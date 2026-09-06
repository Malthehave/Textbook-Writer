"""Deterministic Typst PDF build (guts of build-textbook-pdf)."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import unicodedata
from importlib.resources import files
from pathlib import Path

from md2typst import convert
from pypdf import PdfReader

from textbook_writer.models.product import BlindAnswer, ProductBook, ProductChapter, ProductFigure
from textbook_writer.runtime.quality import inspect_compiled_pdf

CLAIM_MARKER_RE = re.compile(r"\s*\[@[a-z0-9]+(?:-[a-z0-9]+)*\]")
CONCEPT_LINK_RE = re.compile(r"\[([^\]]+)\]\(concept:[^)]+\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]", flags=re.DOTALL)
INLINE_PAREN_MATH_RE = re.compile(r"\\\((.+?)\\\)")
MITEX_IMPORT = '#import "@preview/mitex:0.2.6": *'
PAGE_TOLERANCE_RATIO = 0.15


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
    display_math: list[str] = []

    def replace_display(match: re.Match[str]) -> str:
        latex = (match.group(1) or match.group(2)).strip()
        if "```" in latex:
            raise ValueError("display math cannot contain a fenced-code delimiter")
        index = len(display_math)
        display_math.append(latex)
        return f"\n\nTEXTBOOKDISPLAYMATH{index}TOKEN\n\n"

    prepared = DISPLAY_MATH_RE.sub(replace_display, prepared)
    prepared = INLINE_PAREN_MATH_RE.sub(lambda match: f"${match.group(1)}$", prepared)
    converted = convert(prepared, parser="markdown-it")
    imports: list[str] = []
    body_lines: list[str] = []
    for line in converted.splitlines():
        if line.startswith("#import "):
            imports.append(line)
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    for index, latex in enumerate(display_math):
        token = f"TEXTBOOKDISPLAYMATH{index}TOKEN"
        body = body.replace(token, f"#mitex(```latex\n{latex}\n```)")
    if display_math and MITEX_IMPORT not in imports:
        imports.append(MITEX_IMPORT)
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


def target_page_range(target_pages: int) -> tuple[int, int]:
    """Return inclusive integer page bounds with 15% tolerance."""

    lower = max(1, math.floor(target_pages * (1 - PAGE_TOLERANCE_RATIO)))
    upper = math.ceil(target_pages * (1 + PAGE_TOLERANCE_RATIO))
    return lower, upper


def build_textbook_pdf_file(*, book_path: Path, output_path: Path) -> dict[str, object]:
    """Compile book.json → PDF. Returns measured paths and page count."""

    book = ProductBook.model_validate_json(book_path.read_text(encoding="utf-8"))
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _stage_figure_assets(book, book_path=book_path, output_path=output_path)
    compile_typst(render_product_book(book), output_path)
    solutions_pdf_path: Path | None = None
    if book.plan.solution_mode == "separate":
        solutions_pdf_path = output_path.with_name(
            f"{output_path.stem}-solutions{output_path.suffix}"
        )
        compile_typst(render_solution_manual(book), solutions_pdf_path)
    pages = pdf_page_count(output_path)
    minimum_pages, maximum_pages = target_page_range(book.plan.target_pages)
    report: dict[str, object] = {
        "pdf_path": str(output_path),
        "typst_path": str(output_path.with_suffix(".typ")),
        "actual_pages": pages,
        "target_pages": book.plan.target_pages,
        "minimum_pages": minimum_pages,
        "maximum_pages": maximum_pages,
        "within_tolerance": minimum_pages <= pages <= maximum_pages,
        "tolerance_ratio": PAGE_TOLERANCE_RATIO,
        "title": book.plan.title,
        "chapter_count": len(book.chapters),
        "iteration_mode": book.plan.iteration_mode,
        "solution_mode": book.plan.solution_mode,
    }
    report.update(
        inspect_compiled_pdf(
            pdf_path=output_path,
            plan=book.plan,
            expected_exercises=sum(len(chapter.exercises) for chapter in book.chapters),
        )
    )
    if solutions_pdf_path is not None:
        report["solutions_pdf_path"] = str(solutions_pdf_path)
        report["solutions_pages"] = pdf_page_count(solutions_pdf_path)
    return report


def render_product_book(book: ProductBook) -> str:
    template = files("textbook_writer.runtime").joinpath("textbook.typ").read_text(
        encoding="utf-8"
    )
    source_by_id = {item.source_id: item for item in book.research.sources}
    markdown = ProductMarkdownRenderer()
    quality_slice = book.plan.iteration_mode == "quality-slice"
    body = [
        "#set page(numbering: none)",
        f"#title-page({_string(book.plan.title)}, {_string(book.plan.learning_goal)})",
        "#pagebreak()",
        '#set page(numbering: "1")',
        "#counter(page).update(1)",
    ]
    if not quality_slice:
        body.extend(
            [
                "#outline(title: [Contents], depth: 2)",
                "#pagebreak()",
                "#heading(level: 1)[How to use this book] <how-to-use>",
                f"#prose({markdown.content('Audience: ' + book.plan.audience)}, ())",
                "#v(4pt)",
                f"#prose({markdown.content('Learning goal: ' + book.plan.learning_goal)}, ())",
                "#v(8pt)",
                "",
            ]
        )
    if not quality_slice and book.plan.running_system.strip():
        body.extend(
            [
                "#heading(level: 2)[The running system]",
                f"#prose({markdown.content(book.plan.running_system)}, ())",
                "",
            ]
        )
    if not quality_slice and book.plan.study_path.strip():
        body.extend(
            [
                "#heading(level: 2)[Recommended study path]",
                f"#prose({markdown.content(book.plan.study_path)}, ())",
                "",
            ]
        )
    if not quality_slice and book.plan.implementation_project.strip():
        body.extend(
            [
                "#heading(level: 2)[Implementation project]",
                f"#prose({markdown.content(book.plan.implementation_project)}, ())",
                "",
            ]
        )
    if not quality_slice and book.plan.glossary:
        body.extend(["#heading(level: 2)[Running-system glossary]", ""])
        for item in book.plan.glossary:
            body.append(
                f"#definition({_string(item.name)}, {markdown.content(item.definition)}, ())"
            )
        body.append("")
    exercise_numbers: dict[str, str] = {}
    for chapter_number, chapter in enumerate(book.chapters, start=1):
        if not (quality_slice and chapter_number == 1):
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
                    _source_citations(section.source_refs, source_by_id),
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
            solution_label = (
                f"<answer-{exercise.exercise_id}>"
                if book.plan.solution_mode != "separate"
                else "none"
            )
            body.extend(
                [
                    f"#exercise-box({_string(number)}, {markdown.content(exercise.prompt)}, "
                    f"{solution_label}) <{exercise.exercise_id}>",
                    _source_citations(exercise.source_refs, source_by_id),
                    "",
                ]
            )

    if book.plan.solution_mode != "separate":
        answer_by_ref = {
            answer.exercise_ref: answer
            for chapter_answers in book.answer_keys
            for answer in chapter_answers.answers
        }
        body.append("#pagebreak()")
        body.extend(["#heading(level: 1)[Answer key] <answer-key>", ""])
        for chapter in book.chapters:
            for exercise in chapter.exercises:
                answer = answer_by_ref[exercise.exercise_id]
                answer_text, reasoning_text = _published_solution(
                    answer, mode=book.plan.solution_mode
                )
                body.extend(
                    [
                        f"#solution-box({_string(exercise_numbers[exercise.exercise_id])}, "
                        f"{markdown.content(answer_text)}, "
                        f"{markdown.content(reasoning_text)}, "
                        f"<{exercise.exercise_id}>) <answer-{exercise.exercise_id}>",
                        _source_citations(
                            answer.source_refs or exercise.source_refs, source_by_id
                        ),
                        "",
                    ]
                )

    if not quality_slice:
        body.append("#pagebreak()")
    body.extend(
        [
            (
                "#heading(level: 1)[Sources and further reading] <bibliography>"
                if quality_slice
                else "#heading(level: 1)[Bibliography] <bibliography>"
            ),
            "#set par(justify: false)",
            "",
        ]
    )
    bibliography_sources = book.research.sources
    if quality_slice:
        used_refs = {
            ref
            for chapter in book.chapters
            for refs in [
                *(section.source_refs for section in chapter.sections),
                *(exercise.source_refs for exercise in chapter.exercises),
            ]
            for ref in refs
        }
        bibliography_sources = [
            source for source in book.research.sources if source.source_id in used_refs
        ]
    for source in bibliography_sources:
        author_prefix = ", ".join(source.authors)
        label = f"{author_prefix}. {source.title}" if author_prefix else source.title
        if source.publication_year is not None:
            label += f" ({source.publication_year})"
        accessed = f" Accessed {_escape(source.accessed_date)}." if source.accessed_date else ""
        body.append(
            f"- {_escape(label)} — {_escape(source.authority.title())}. "
            f"#link({_string(str(source.url))})[{_escape(str(source.url))}].{accessed} "
            f"<{source.source_id}>"
        )
    body.append("")
    output = [template.rstrip(), ""]
    if markdown.imports:
        output.extend(markdown.imports)
        output.append("")
    output.extend(body)
    return "\n".join(output).rstrip() + "\n"


def render_solution_manual(book: ProductBook) -> str:
    """Render independently verified full solutions as a companion PDF."""

    template = files("textbook_writer.runtime").joinpath("textbook.typ").read_text(
        encoding="utf-8"
    )
    source_by_id = {item.source_id: item for item in book.research.sources}
    exercise_by_ref = {
        exercise.exercise_id: (chapter_number, exercise_number, exercise)
        for chapter_number, chapter in enumerate(book.chapters, start=1)
        for exercise_number, exercise in enumerate(chapter.exercises, start=1)
    }
    markdown = ProductMarkdownRenderer()
    body = [
        "#set page(numbering: none)",
        f"#title-page({_string(book.plan.title + ' — Solutions')}, "
        f"{_string('Independently solved and verified answer key')})",
        "#pagebreak()",
        '#set page(numbering: "1")',
        "#counter(page).update(1)",
        "#heading(level: 1)[Solutions]",
        "",
    ]
    for chapter_answers in book.answer_keys:
        chapter = next(
            item for item in book.chapters if item.chapter_id == chapter_answers.chapter_ref
        )
        body.extend([f"#heading(level: 2)[{_escape(chapter.title)}]", ""])
        for answer in chapter_answers.answers:
            chapter_number, exercise_number, exercise = exercise_by_ref[answer.exercise_ref]
            number = f"{chapter_number}.{exercise_number}"
            body.extend(
                [
                    f"#solution-box({_string(number)}, {markdown.content(answer.answer)}, "
                    f"{markdown.content(answer.reasoning)}, none)",
                    _source_citations(
                        answer.source_refs or exercise.source_refs, source_by_id
                    ),
                    "",
                ]
            )
    body.extend(["#heading(level: 1)[Sources]", "#set par(justify: false)", ""])
    for source in book.research.sources:
        author_prefix = ", ".join(source.authors)
        label = f"{author_prefix}. {source.title}" if author_prefix else source.title
        if source.publication_year is not None:
            label += f" ({source.publication_year})"
        body.append(
            f"- {_escape(label)}. #link({_string(str(source.url))})"
            f"[{_escape(str(source.url))}] <{source.source_id}>"
        )
    output = [template.rstrip(), ""]
    if markdown.imports:
        output.extend(markdown.imports)
        output.append("")
    output.extend(body)
    return "\n".join(output).rstrip() + "\n"


def _published_solution(answer: BlindAnswer, *, mode: str) -> tuple[str, str]:
    if mode == "full":
        return answer.answer, answer.reasoning
    return answer.rubric or answer.answer, ""


def _source_citations(source_refs: list[str], source_by_id: dict[str, object]) -> str:
    if not source_refs:
        return ""
    links = []
    for ref in dict.fromkeys(source_refs):
        number = list(source_by_id).index(ref) + 1
        links.append(f"#link(<{ref}>)[{_escape(f'[{number}]')}]")
    return (
        "#align(right)[#text(font: \"Avenir Next\", size: 7pt, fill: muted)["
        + " · ".join(links)
        + "]]"
    )


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
    normalized = value.translate({0x00A0: 0x20, 0x2007: 0x20, 0x202F: 0x20})
    return json.dumps(normalized, ensure_ascii=False)


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
