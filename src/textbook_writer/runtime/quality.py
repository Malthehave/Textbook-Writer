"""Deterministic scope forecasting and publication-integrity checks."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from textbook_writer.models.product import BlindAnswers, ProductBookPlan, ProductChapter

WORD_RE = re.compile(r"\b[\w’'-]+\b", flags=re.UNICODE)
PLACEHOLDER_MARKERS = (
    "learner response required",
    "learner reasoning required",
    "no draft answer is supplied",
    "no draft reasoning is supplied",
)


def word_count(value: str) -> int:
    return len(WORD_RE.findall(value))


def forecast_book_pages(
    *,
    plan: ProductBookPlan,
    chapters: list[ProductChapter],
    answer_keys: list[BlindAnswers],
    source_count: int,
) -> dict[str, Any]:
    """Estimate complete-artifact pages from actual content and remaining plan budgets.

    This is deliberately conservative. It is a planning signal; measured Typst output
    remains authoritative.
    """

    chapter_by_id = {chapter.chapter_id: chapter for chapter in chapters}
    answers_by_id = {answers.chapter_ref: answers for answers in answer_keys}
    prose_words = 0
    exercise_words = 0
    solution_words = 0
    figure_count = 0
    actual_chapters = 0

    for planned in plan.chapters:
        chapter = chapter_by_id.get(planned.chapter_id)
        if chapter is None:
            prose_words += planned.target_words
            exercise_words += planned.exercise_count * (75 if plan.iteration_mode == "prototype" else 140)
            if plan.solution_mode == "full":
                solution_words += planned.exercise_count * 260
            elif plan.solution_mode == "concise":
                solution_words += planned.exercise_count * 90
            figure_count += int(planned.visual is not None)
            continue

        actual_chapters += 1
        prose_words += word_count(chapter.bridge_from_previous)
        prose_words += word_count(chapter.introduction)
        prose_words += sum(word_count(section.markdown) for section in chapter.sections)
        prose_words += word_count(chapter.summary)
        exercise_words += sum(word_count(exercise.prompt) for exercise in chapter.exercises)
        figure_count += len(chapter.figures)
        answers = answers_by_id.get(chapter.chapter_id)
        if plan.solution_mode != "separate":
            if answers is None:
                per_answer = 260 if plan.solution_mode == "full" else 90
                solution_words += len(chapter.exercises) * per_answer
            else:
                for answer in answers.answers:
                    if plan.solution_mode == "full":
                        solution_words += word_count(answer.answer) + word_count(answer.reasoning)
                    else:
                        solution_words += word_count(answer.rubric or answer.answer)

    compact_slice = plan.iteration_mode == "quality-slice"
    components = {
        "front_matter": 1.0 if compact_slice else 3.0,
        "chapter_prose": prose_words / 430,
        "figures": figure_count * 0.65,
        "exercises": exercise_words / 300,
        "solutions": solution_words / 330,
        "bibliography": max(0.4, source_count / 16) if compact_slice else max(1.0, source_count / 12),
    }
    projected = math.ceil(sum(components.values()))
    lower = max(1, math.floor(plan.target_pages * 0.85))
    upper = math.ceil(plan.target_pages * 1.15)
    return {
        "projected_pages": projected,
        "target_pages": plan.target_pages,
        "minimum_pages": lower,
        "maximum_pages": upper,
        "projected_within_tolerance": lower <= projected <= upper,
        "actual_chapters": actual_chapters,
        "planned_chapters": len(plan.chapters),
        "content": {
            "prose_words": prose_words,
            "exercise_words": exercise_words,
            "solution_words": solution_words,
            "figure_count": figure_count,
        },
        "component_pages": {key: round(value, 1) for key, value in components.items()},
    }


def inspect_compiled_pdf(
    *, pdf_path: Path, plan: ProductBookPlan, expected_exercises: int
) -> dict[str, Any]:
    """Run deterministic checks against the learner-visible compiled artifact."""

    reader = PdfReader(pdf_path.resolve())
    page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    full_text = "\n".join(page_text)
    lowered = full_text.lower()
    issues: list[dict[str, Any]] = []
    blank_pages = [index + 1 for index, text in enumerate(page_text) if len(text) < 12]
    if blank_pages:
        issues.append(
            {
                "category": "blank-pages",
                "pages": blank_pages,
                "message": "Compiled PDF contains effectively blank pages.",
            }
        )
    found_placeholders = [marker for marker in PLACEHOLDER_MARKERS if marker in lowered]
    if found_placeholders:
        issues.append(
            {
                "category": "solutions",
                "markers": found_placeholders,
                "message": "Compiled PDF exposes placeholder solution text.",
            }
        )
    normalized_title = " ".join(plan.title.lower().split())
    normalized_cover = " ".join((page_text[0] if page_text else "").lower().split())
    if normalized_title not in normalized_cover:
        issues.append(
            {
                "category": "title",
                "message": "Published title was not found on the opening page.",
            }
        )
    bounds_issue = _opening_page_bounds_issue(pdf_path)
    if bounds_issue is not None:
        issues.append(bounds_issue)
    if plan.solution_mode != "separate":
        answer_headings = len(re.findall(r"\bAnswer\s+\d+\.\d+\b", full_text))
        if answer_headings < expected_exercises:
            issues.append(
                {
                    "category": "solutions",
                    "message": (
                        f"Found {answer_headings} answer headings for "
                        f"{expected_exercises} exercises."
                    ),
                }
            )
    minimum = max(1, math.floor(plan.target_pages * 0.85))
    maximum = math.ceil(plan.target_pages * 1.15)
    pages = len(reader.pages)
    if not minimum <= pages <= maximum:
        issues.append(
            {
                "category": "page-fit",
                "message": f"Measured {pages} pages; allowed range is {minimum}-{maximum}.",
            }
        )
    return {
        "quality_passed": not issues,
        "quality_issues": issues,
        "blank_pages": blank_pages,
        "extracted_words": word_count(full_text),
    }


def _opening_page_bounds_issue(pdf_path: Path) -> dict[str, Any] | None:
    """Detect text whose bounding box escapes the cover page media box."""

    if shutil.which("pdftotext") is None:
        return None
    result = subprocess.run(
        ["pdftotext", "-f", "1", "-l", "1", "-bbox", str(pdf_path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        root = ET.fromstring(result.stdout)
    except ET.ParseError:
        return None
    page = next((node for node in root.iter() if node.tag.endswith("page")), None)
    if page is None:
        return None
    try:
        width = float(page.attrib["width"])
        height = float(page.attrib["height"])
    except (KeyError, ValueError):
        return None
    escaped: list[str] = []
    for word in (node for node in page.iter() if node.tag.endswith("word")):
        try:
            x_min = float(word.attrib["xMin"])
            x_max = float(word.attrib["xMax"])
            y_min = float(word.attrib["yMin"])
            y_max = float(word.attrib["yMax"])
        except (KeyError, ValueError):
            continue
        if x_min < 1 or y_min < 1 or x_max > width - 1 or y_max > height - 1:
            escaped.append(" ".join("".join(word.itertext()).split()))
    if not escaped:
        return None
    return {
        "category": "title-bounds",
        "page": 1,
        "message": "Opening-page text extends beyond the printable page bounds: "
        + ", ".join(filter(None, escaped[:6])),
    }
