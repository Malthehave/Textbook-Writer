"""Deterministic PDF publication for compact production books."""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from hashlib import sha256
from importlib.resources import files
from pathlib import Path

from pydantic import Field

from textbook_writer.models.base import Model
from textbook_writer.models.product import (
    ProductBook,
    ProductChapter,
    ProductFigure,
)
from textbook_writer.publishing.pdf import PdfInspection, inspect_pdf, render_pdf_pages
from textbook_writer.publishing.typst import ProductMarkdownRenderer, compile_typst


def book_output_stem(title: str, *, max_length: int = 80) -> str:
    """Filesystem-safe stem derived from the book title (for PDF/Typst filenames)."""

    normalized = unicodedata.normalize("NFKD", title.strip())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if not slug:
        slug = "textbook"
    return slug[:max_length].rstrip("-") or "textbook"


class ProductBuildReport(Model):
    book_path: str
    typst_path: str
    pdf_path: str
    inspection_path: str
    page_image_paths: list[str]
    content_hash: str
    target_pages: int = Field(ge=1)
    page_tolerance: int = Field(ge=0)
    actual_pages: int = Field(ge=1)
    within_page_tolerance: bool
    source_count: int = Field(ge=2)
    frozen_evidence_chunk_count: int = Field(ge=1)
    citation_count: int = Field(ge=1)
    researched_topic_count: int = Field(ge=1)
    figure_count: int = Field(ge=0)
    exercise_count: int = Field(ge=1)
    verified_exercise_count: int = Field(ge=1)
    inspection: PdfInspection


def build_product_book(
    *, book_path: Path, output_path: Path, page_tolerance: int
) -> ProductBuildReport:
    book = ProductBook.model_validate_json(book_path.read_text(encoding="utf-8"))
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _stage_figure_assets(book, book_path=book_path, output_path=output_path)
    compile_typst(render_product_book(book), output_path)
    inspection = inspect_pdf(output_path)
    inspection_path = output_path.with_suffix(".inspection.json")
    inspection_path.write_text(
        json.dumps(inspection.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    page_paths = render_pdf_pages(
        output_path, output_path.parent / f"{output_path.stem}-pages"
    )
    canonical = json.dumps(
        book.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    exercise_count = sum(len(chapter.exercises) for chapter in book.chapters)
    figure_count = sum(len(chapter.figures) for chapter in book.chapters)
    verified_count = sum(
        len(verification.verdicts) for verification in book.exercise_verifications
    )
    report = ProductBuildReport(
        book_path=str(book_path.resolve()),
        typst_path=str(output_path.with_suffix(".typ")),
        pdf_path=str(output_path),
        inspection_path=str(inspection_path),
        page_image_paths=[str(path) for path in page_paths],
        content_hash=f"sha256:{sha256(canonical).hexdigest()}",
        target_pages=book.plan.target_pages,
        page_tolerance=page_tolerance,
        actual_pages=inspection.pages,
        within_page_tolerance=(
            book.plan.target_pages - page_tolerance
            <= inspection.pages
            <= book.plan.target_pages + page_tolerance
        ),
        source_count=len(book.dossier.sources),
        frozen_evidence_chunk_count=len(book.evidence_index),
        citation_count=len(book.citation_ledger),
        researched_topic_count=len(book.dossier.topics),
        figure_count=figure_count,
        exercise_count=exercise_count,
        verified_exercise_count=verified_count,
        inspection=inspection,
    )
    output_path.with_suffix(".build.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def render_product_book(book: ProductBook) -> str:
    template = files("textbook_writer.publishing").joinpath("textbook.typ").read_text(
        encoding="utf-8"
    )
    # A fixed break before every chapter and back-matter section can consume the
    # entire budget of a short multi-chapter guide. Choose compact flow from both
    # the requested size and chapter count, not from page count alone.
    compact_threshold = max(8, 2 * len(book.chapters) + 4)
    compact_book = book.plan.target_pages <= compact_threshold
    if compact_book and len(book.chapters) >= 3:
        template = _dense_compact_template(template)
    source_by_id = {item.source_id: item for item in book.dossier.sources}
    chunk_by_id = {item.chunk_ref: item for item in book.evidence_index}
    citations_by_pair: dict[tuple[str, str], list[object]] = {}
    for citation in book.citation_ledger:
        citations_by_pair.setdefault(
            (citation.content_ref, citation.source_ref), []
        ).append(citation)
    acquisition_by_source = {
        item.source_id: item for item in book.source_archive.acquisitions
    }
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
                "Every included topic was supported by at least two credible sources from independent hosts, including an official or practitioner signal of real-world relevance. Exercises were answered independently before their answer keys were approved."
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
        body.extend(
            [
                f"#heading(level: 1)[Chapter {chapter_number}: {_escape(chapter.title)}] <{chapter.chapter_id}>",
            ]
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
                    _source_line(
                        section.source_refs,
                        section.section_id,
                        source_by_id,
                        citations_by_pair,
                        chunk_by_id,
                    ),
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
                f"#heading(level: 2)[Chapter {chapter_number} exercises] <exercises-{chapter.chapter_id}>",
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
                    _source_line(
                        exercise.source_refs,
                        exercise.exercise_id,
                        source_by_id,
                        citations_by_pair,
                        chunk_by_id,
                    ),
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
                    f"{markdown.content(exercise.answer)}, {markdown.content(exercise.reasoning)}, "
                    f"<{exercise.exercise_id}>) <answer-{exercise.exercise_id}>",
                    _source_line(
                        exercise.source_refs,
                        exercise.exercise_id,
                        source_by_id,
                        citations_by_pair,
                        chunk_by_id,
                    ),
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
    for source in book.dossier.sources:
        label = source.title
        if source.publication_year is not None:
            label += f" ({source.publication_year})"
        body.append(
            f"- {_escape(label)} — {_escape(source.authority.title())}. "
            f"#link({_string(str(source.url))})[Open source]. "
            f"Frozen snapshot: "
            f"{_escape(acquisition_by_source[source.source_id].content_hash[:23])}… "
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
    """Tighten multi-chapter short guides without changing semantic content."""

    replacements = {
        "margin: (top: 21mm, bottom: 20mm, left: 23mm, right: 23mm)": (
            "margin: (top: 17mm, bottom: 16mm, left: 20mm, right: 20mm)"
        ),
        'size: 10.5pt, fill: ink': 'size: 9.6pt, fill: ink',
        "leading: 0.74em, spacing: 1.35em": (
            "leading: 0.66em, spacing: 0.95em"
        ),
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
        "inset: 11pt, above: 6pt, below: 10pt": (
            "inset: 9pt, above: 5pt, below: 7pt"
        ),
    }
    for old, new in replacements.items():
        template = template.replace(old, new)
    return template


def _source_line(
    source_refs: list[str],
    content_ref: str,
    source_by_id: dict[str, object],
    citations_by_pair: dict[tuple[str, str], list[object]],
    chunk_by_id: dict[str, object],
) -> str:
    links = []
    for ref in dict.fromkeys(source_refs):
        source = source_by_id[ref]
        citations = citations_by_pair[(content_ref, ref)]
        locators = []
        for citation in citations:
            chunk = chunk_by_id[citation.chunk_ref]
            locators.append(f"p. {chunk.page}" if chunk.page is not None else "frozen passage")
        locator = ", ".join(dict.fromkeys(locators))
        links.append(
            f"#link({_string(str(source.url))})"
            f"[{_escape(source.title)} ({_escape(locator)})]"
        )
    return "#text(size: 7.5pt, fill: muted)[Sources: " + " · ".join(links) + "]"


def _figures_for_section(
    chapter: ProductChapter, section_id: str, *, section_index: int
) -> list[ProductFigure]:
    """Place explicitly anchored figures, plus unanchored ones after the first section."""

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
