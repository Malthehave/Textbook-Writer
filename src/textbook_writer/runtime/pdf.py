"""Deterministic Typst PDF build (guts of build-textbook-pdf)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from importlib.resources import files
from pathlib import Path

from md2typst import convert
from pypdf import PdfReader

from textbook_writer.models.product import ProductBook, ProductChapter, ProductFigure

CLAIM_MARKER_RE = re.compile(r"\s*\[@[a-z0-9]+(?:-[a-z0-9]+)*\]")
CONCEPT_LINK_RE = re.compile(r"\[([^\]]+)\]\(concept:[^)]+\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def book_output_stem(title: str, *, max_length: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", title.strip())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if not slug:
        slug = "textbook"
    return slug[:max_length].rstrip("-") or "textbook"


def prepare_product_markdown(markdown: str) -> str:
    text = CLAIM_MARKER_RE.sub("", markdown)
    text = CONCEPT_LINK_RE.sub(r"\1", text)
    return text.strip()


def markdown_to_typst_content(markdown: str) -> tuple[str, tuple[str, ...]]:
    prepared = prepare_product_markdown(markdown)
    if not prepared:
        return "[]", ()
    converted = convert(prepared, parser="markdown-it")
    imports: list[str] = []
    body_lines: list[str] = []
    for line in converted.splitlines():
        if line.startswith("#import "):
            imports.append(line)
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    if not body:
        return "[]", tuple(dict.fromkeys(imports))
    return f"[\n{body}\n]", tuple(dict.fromkeys(imports))


class ProductMarkdownRenderer:
    def __init__(self) -> None:
        self.imports: list[str] = []

    def content(self, markdown: str) -> str:
        block, found = markdown_to_typst_content(markdown)
        for item in found:
            if item not in self.imports:
                self.imports.append(item)
        return block


def compile_typst(source: str, output_path: Path, *, typst_binary: str = "typst") -> Path:
    if shutil.which(typst_binary) is None:
        raise RuntimeError(f"Typst compiler not found: {typst_binary}")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_path = output_path.with_suffix(".typ")
    source_path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [typst_binary, "compile", str(source_path), str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Typst compilation failed:\n{result.stderr.strip()}")
    return output_path


def _plain(markdown: str) -> str:
    text = CLAIM_MARKER_RE.sub("", markdown)
    text = CONCEPT_LINK_RE.sub(r"\1", text)
    text = BOLD_RE.sub(r"\1", text)
    paragraphs = [
        " ".join(part.split())
        for part in re.split(r"\n\s*\n", text)
        if part.strip()
    ]
    return "\n\n".join(paragraphs)


def pdf_page_count(path: Path) -> int:
    return len(PdfReader(path.resolve()).pages)


def build_textbook_pdf_file(*, book_path: Path, output_path: Path) -> dict[str, object]:
    """Compile book.json → PDF. Returns measured paths and page count."""

    book = ProductBook.model_validate_json(book_path.read_text(encoding="utf-8"))
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _stage_figure_assets(book, book_path=book_path, output_path=output_path)
    compile_typst(render_product_book(book), output_path)
    pages = pdf_page_count(output_path)
    return {
        "pdf_path": str(output_path),
        "typst_path": str(output_path.with_suffix(".typ")),
        "actual_pages": pages,
        "target_pages": book.plan.target_pages,
        "title": book.plan.title,
        "chapter_count": len(book.chapters),
    }


def render_product_book(book: ProductBook) -> str:
    template = files("textbook_writer.runtime").joinpath("textbook.typ").read_text(
        encoding="utf-8"
    )
    compact_book = len(book.chapters) >= 3
    if compact_book:
        template = _dense_compact_template(template)
    source_by_id = {item.source_id: item for item in book.research.sources}
    markdown = ProductMarkdownRenderer()
    body = [
        "#set page(numbering: none)",
        f"#title-page({_string(book.plan.title)}, {_string(book.plan.learning_goal)})",
        "#pagebreak()",
        '#set page(numbering: "1")',
        "#counter(page).update(1)",
        "#outline(title: [Contents], depth: 2)",
    ]
    if not compact_book:
        body.append("#pagebreak()")
    body.extend(
        [
            "#heading(level: 1)[How to use this book] <how-to-use>",
            f"#prose({markdown.content('Audience: ' + book.plan.audience)}, ())",
            "#v(4pt)",
            f"#prose({markdown.content('Learning goal: ' + book.plan.learning_goal)}, ())",
            "#v(8pt)",
            "#callout(\"Research standard\", \"key-insight\", "
            + markdown.content(
                "Every included topic was supported by at least two credible sources from "
                "independent hosts, including an official or practitioner signal of "
                "real-world relevance. Exercises were answered independently before their "
                "answer keys were approved."
            )
            + ", ())",
            "",
        ]
    )
    if book.plan.running_system.strip():
        body.extend(
            [
                "#heading(level: 2)[The running system]",
                f"#prose({markdown.content(book.plan.running_system)}, ())",
                "",
            ]
        )
    if book.plan.glossary:
        body.extend(["#heading(level: 2)[Running-system glossary]", ""])
        for item in book.plan.glossary:
            body.append(
                f"#definition({_string(item.name)}, {markdown.content(item.definition)}, ())"
            )
        body.append("")
    exercise_numbers: dict[str, str] = {}
    for chapter_number, chapter in enumerate(book.chapters, start=1):
        if not compact_book or chapter_number == 1:
            body.append("#pagebreak()")
        body.append(
            f"#heading(level: 1)[Chapter {chapter_number}: {_escape(chapter.title)}] "
            f"<{chapter.chapter_id}>"
        )
        if chapter.bridge_from_previous.strip():
            body.extend(
                [
                    "#callout(\"From the previous chapter\", \"key-insight\", "
                    + markdown.content(chapter.bridge_from_previous)
                    + ", ())",
                    "",
                ]
            )
        body.extend(
            [
                f"#prose({markdown.content(chapter.introduction)}, ())",
                f"#objective-box({_array(chapter.learning_outcomes)})",
                "",
            ]
        )
        placed_figure_ids: set[str] = set()
        for section_index, section in enumerate(chapter.sections):
            body.extend(
                [
                    f"#heading(level: 2)[{_escape(section.title)}] <{section.section_id}>",
                    f"#prose({markdown.content(section.markdown)}, ())",
                    _source_line(section.source_refs, source_by_id),
                    "",
                ]
            )
            for figure in _figures_for_section(
                chapter, section.section_id, section_index=section_index
            ):
                body.extend([_render_product_figure(figure), ""])
                placed_figure_ids.add(figure.figure_id)
        for figure in chapter.figures:
            if figure.figure_id not in placed_figure_ids:
                body.extend([_render_product_figure(figure), ""])
        body.extend(
            [
                "#callout(\"Chapter summary\", \"chapter-summary\", "
                + markdown.content(chapter.summary)
                + ", ())",
                f"#heading(level: 2)[Chapter {chapter_number} exercises] "
                f"<exercises-{chapter.chapter_id}>",
                "",
            ]
        )
        for exercise_number, exercise in enumerate(chapter.exercises, start=1):
            number = f"{chapter_number}.{exercise_number}"
            exercise_numbers[exercise.exercise_id] = number
            body.extend(
                [
                    f"#exercise-box({_string(number)}, {markdown.content(exercise.prompt)}, "
                    f"<answer-{exercise.exercise_id}>) <{exercise.exercise_id}>",
                    _source_line(exercise.source_refs, source_by_id),
                    "",
                ]
            )

    if not compact_book:
        body.append("#pagebreak()")
    body.extend(["#heading(level: 1)[Answer key] <answer-key>", ""])
    for chapter in book.chapters:
        for exercise in chapter.exercises:
            body.extend(
                [
                    f"#solution-box({_string(exercise_numbers[exercise.exercise_id])}, "
                    f"{markdown.content(exercise.answer)}, "
                    f"{markdown.content(exercise.reasoning)}, "
                    f"<{exercise.exercise_id}>) <answer-{exercise.exercise_id}>",
                    _source_line(exercise.source_refs, source_by_id),
                    "",
                ]
            )

    if not compact_book:
        body.append("#pagebreak()")
    body.extend(
        [
            "#heading(level: 1)[Bibliography] <bibliography>",
            "#set par(justify: false)",
            "",
        ]
    )
    for source in book.research.sources:
        label = source.title
        if source.publication_year is not None:
            label += f" ({source.publication_year})"
        body.append(
            f"- {_escape(label)} — {_escape(source.authority.title())}. "
            f"#link({_string(str(source.url))})[Open source]. "
            f"<{source.source_id}>"
        )
    body.append("")
    output = [template.rstrip(), ""]
    if markdown.imports:
        output.extend(markdown.imports)
        output.append("")
    output.extend(body)
    return "\n".join(output).rstrip() + "\n"


def _dense_compact_template(template: str) -> str:
    replacements = {
        "margin: (top: 21mm, bottom: 20mm, left: 23mm, right: 23mm)": (
            "margin: (top: 17mm, bottom: 16mm, left: 20mm, right: 20mm)"
        ),
        "size: 10.5pt, fill: ink": "size: 9.6pt, fill: ink",
        "leading: 0.74em, spacing: 1.35em": "leading: 0.66em, spacing: 0.95em",
        "above: 1.8em, below: 1.1em": "above: 1.35em, below: 0.8em",
        "size: 23pt, weight:": "size: 20pt, weight:",
        "above: 1.4em, below: 0.7em": "above: 1.05em, below: 0.5em",
        "size: 15pt, weight:": "size: 13.5pt, weight:",
        "inset: 13pt,": "inset: 10pt,",
        "below: 12pt,": "below: 8pt,",
        "#v(6pt)\n  #for item": "#v(4pt)\n  #for item",
        "#v(3pt)\n  ]": "#v(2pt)\n  ]",
        "inset: 11pt,\n  above: 8pt,\n  below: 10pt,": (
            "inset: 9pt,\n  above: 6pt,\n  below: 7pt,"
        ),
        "radius: 4pt, inset: 11pt, above: 6pt, below: 9pt": (
            "radius: 4pt, inset: 9pt, above: 5pt, below: 7pt"
        ),
        "inset: 11pt, above: 6pt, below: 10pt": "inset: 9pt, above: 5pt, below: 7pt",
    }
    for old, new in replacements.items():
        template = template.replace(old, new)
    return template


def _source_line(source_refs: list[str], source_by_id: dict[str, object]) -> str:
    if not source_refs:
        return ""
    links = []
    for ref in dict.fromkeys(source_refs):
        source = source_by_id[ref]
        links.append(f"#link({_string(str(source.url))})[{_escape(source.title)}]")
    return "#text(size: 7.5pt, fill: muted)[Sources: " + " · ".join(links) + "]"


def _figures_for_section(
    chapter: ProductChapter, section_id: str, *, section_index: int
) -> list[ProductFigure]:
    anchored = [
        figure for figure in chapter.figures if figure.section_ref == section_id
    ]
    if section_index == 0:
        unanchored = [
            figure for figure in chapter.figures if figure.section_ref is None
        ]
        return [*anchored, *unanchored]
    return anchored


def _render_product_figure(figure: ProductFigure) -> str:
    image_path = f"assets/figures/{Path(figure.asset_path).name}"
    return (
        f"#figure(\n"
        f"  image({_string(image_path)}, width: 100%),\n"
        f"  caption: [{_escape(figure.caption)}],\n"
        f") <{figure.figure_id}>"
    )


def _stage_figure_assets(
    book: ProductBook, *, book_path: Path, output_path: Path
) -> None:
    workspace = book_path.resolve().parent.parent
    target_dir = output_path.parent / "assets" / "figures"
    target_dir.mkdir(parents=True, exist_ok=True)
    for chapter in book.chapters:
        for figure in chapter.figures:
            source = workspace / figure.asset_path
            if not source.is_file():
                raise FileNotFoundError(f"chapter figure asset missing at {source}")
            shutil.copy2(source, target_dir / source.name)


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _array(values: list[str]) -> str:
    rendered = ", ".join(_string(value) for value in values)
    return f"({rendered},)" if len(values) == 1 else f"({rendered})"


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("#", "\\#")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )
