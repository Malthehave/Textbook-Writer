"""Deterministic content-quality checks used by tools and unit tests."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from textbook_writer.models.product import (
    PlannedVisual,
    ProductBookPlan,
    ProductChapter,
    ResearchDossier,
    RunningSystemComponent,
)


META_HEADER_RE = re.compile(r"(?im)^\s*\*\*\s*(Topics|Sources)\s*:\s*\*\*")
RAW_SOURCE_ID_RE = re.compile(r"\bsource-\d+\b", re.IGNORECASE)
NON_LATIN_RE = re.compile(
    r"[\u0400-\u04FF\u0600-\u06FF\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]"
)
MATH_OUTCOME_RE = re.compile(
    r"\b(ppo|objective|surrogate|loss function|gradient|equation|deriv)\w*\b",
    re.IGNORECASE,
)
MATH_BODY_RE = re.compile(r"(\${1,2}.+?\${1,2})|(\\\(.+?\\\))|(\\begin\{equation\})")


def sanitize_plain_english_title(title: str) -> str:
    cleaned = NON_LATIN_RE.sub("", title)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*([-–—/:])\s*", r" \1 ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—/:.")
    return cleaned


def default_glossary(
    running_system: str, chapters: list[Any]
) -> list[RunningSystemComponent]:
    first_chapter = chapters[0].chapter_id if chapters else "chapter-01"
    parts = [
        part.strip(" .;")
        for part in re.split(r",| and |;|/", running_system)
        if len(part.strip(" .;")) >= 3
    ]
    glossary: list[RunningSystemComponent] = []
    seen: set[str] = set()
    for index, part in enumerate(parts[:10], start=1):
        name = part[:48]
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        glossary.append(
            RunningSystemComponent(
                component_id=f"component-{index:02d}",
                name=name,
                definition=(
                    f"{name} is a named part of the book's running system and is "
                    "introduced when the learner first needs it."
                ),
                first_chapter_ref=first_chapter,
            )
        )
    return glossary


def ensure_plan_visuals(plan: ProductBookPlan) -> ProductBookPlan:
    """Guarantee running system, glossary, diagram slots, and plain-English titles."""

    running_system = plan.running_system.strip() or (
        "A shared research system that the learner builds across chapters for: "
        f"{plan.learning_goal}"
    )
    title = sanitize_plain_english_title(plan.title) or plan.title
    chapters = []
    for chapter in plan.chapters:
        visual = chapter.visual
        if visual is None:
            visual = PlannedVisual(
                visual_id=f"visual-{chapter.chapter_id}",
                diagram_type="process-flow",
                learning_purpose=(
                    f"Show how the shared running system advances in {chapter.title}."
                ),
                caption=f"{sanitize_plain_english_title(chapter.title)}: control flow",
            )
        chapters.append(
            chapter.model_copy(
                update={
                    "title": sanitize_plain_english_title(chapter.title) or chapter.title,
                    "visual": visual,
                }
            )
        )
    glossary = list(plan.glossary) or default_glossary(running_system, chapters)
    return plan.model_copy(
        update={
            "title": title,
            "running_system": running_system,
            "glossary": glossary,
            "chapters": chapters,
        }
    )


def ensure_chapter_bridges(
    plan: ProductBookPlan, chapters: list[ProductChapter]
) -> list[ProductChapter]:
    plan_by_id = {item.chapter_id: item for item in plan.chapters}
    ensured: list[ProductChapter] = []
    for index, chapter in enumerate(chapters):
        if index == 0:
            ensured.append(chapter.model_copy(update={"bridge_from_previous": ""}))
            continue
        if chapter.bridge_from_previous.strip():
            ensured.append(chapter)
            continue
        previous = chapters[index - 1]
        purpose = plan_by_id[chapter.chapter_id].purpose
        bridge = (
            f"You already have the working pieces from {previous.title}, especially "
            f"its outcomes around {previous.learning_outcomes[0].rstrip('.')}. "
            f"This chapter extends the same running system by {purpose.rstrip('.')}."
        )
        ensured.append(chapter.model_copy(update={"bridge_from_previous": bridge}))
    return ensured


def validate_chapter_content(
    chapter_plan: Any,
    dossier: ResearchDossier,
    chapter: ProductChapter,
    *,
    chapter_index: int | None = None,
) -> None:
    if chapter.chapter_id != chapter_plan.chapter_id:
        raise RuntimeError("writer changed the planned chapter ID")
    if chapter.learning_outcomes != chapter_plan.learning_outcomes:
        raise RuntimeError("writer changed the approved learning outcomes")
    if len(chapter.exercises) != chapter_plan.exercise_count:
        raise RuntimeError("writer changed the approved exercise count")
    if not chapter.figures:
        raise RuntimeError(f"chapter {chapter.chapter_id} is missing its required diagram figure")
    if NON_LATIN_RE.search(chapter.title):
        raise RuntimeError(f"chapter {chapter.chapter_id} title must be plain English")
    body_texts = [
        chapter.introduction,
        chapter.summary,
        chapter.bridge_from_previous,
        *[section.markdown for section in chapter.sections],
    ]
    for text in body_texts:
        if META_HEADER_RE.search(text):
            raise RuntimeError(
                f"chapter {chapter.chapter_id} contains scaffolding **Topics:**/**Sources:** headers"
            )
        if RAW_SOURCE_ID_RE.search(text):
            raise RuntimeError(
                f"chapter {chapter.chapter_id} exposes raw source IDs in learner-facing prose"
            )
    if chapter_index is not None and chapter_index > 0 and not chapter.bridge_from_previous.strip():
        raise RuntimeError(f"chapter {chapter.chapter_id} is missing bridge_from_previous")
    needs_math = any(MATH_OUTCOME_RE.search(outcome) for outcome in chapter.learning_outcomes)
    chapter_body = "\n".join(body_texts)
    if needs_math and not MATH_BODY_RE.search(chapter_body):
        raise RuntimeError(
            f"chapter {chapter.chapter_id} outcomes require math but the body has no formula"
        )
    for figure in chapter.figures:
        mention_corpus = "\n".join(section.markdown for section in chapter.sections)
        if figure.figure_id not in mention_corpus and "figure" not in mention_corpus.casefold():
            raise RuntimeError(
                f"chapter {chapter.chapter_id} never refers to its diagram in section prose"
            )
    allowed_topics = {
        *chapter_plan.topic_refs,
        *chapter_plan.supporting_topic_refs,
    }
    source_ids = {item.source_id for item in dossier.sources}
    section_ids = {section.section_id for section in chapter.sections}
    for section in chapter.sections:
        if not set(section.topic_refs).issubset(allowed_topics):
            raise RuntimeError(f"section {section.section_id} escapes its chapter topics")
        if not set(section.source_refs).issubset(source_ids):
            raise RuntimeError(f"section {section.section_id} cites an unknown source")
    for figure in chapter.figures:
        if figure.section_ref is not None and figure.section_ref not in section_ids:
            raise RuntimeError(
                f"figure {figure.figure_id} references unknown section {figure.section_ref}"
            )
    covered_topics = {ref for section in chapter.sections for ref in section.topic_refs}
    if not set(chapter_plan.topic_refs).issubset(covered_topics):
        raise RuntimeError(f"chapter {chapter.chapter_id} does not teach every primary topic")
    for exercise in chapter.exercises:
        if exercise.learning_outcome not in chapter.learning_outcomes:
            brief = (chapter_plan.assessment_brief or "").casefold()
            target = exercise.learning_outcome.casefold().strip().rstrip(".")
            brief_sentences = [
                item.strip() for item in re.split(r"(?<=[.!?])\s+", brief) if item.strip()
            ]
            assessment_match = target in brief or any(
                SequenceMatcher(None, target, sentence.rstrip(".")).ratio() >= 0.45
                for sentence in brief_sentences
            )
            if not target or not (assessment_match or brief):
                raise RuntimeError(
                    f"exercise {exercise.exercise_id} targets an unknown outcome or assessment product"
                )
        if not set(exercise.source_refs).issubset(source_ids):
            raise RuntimeError(f"exercise {exercise.exercise_id} cites an unknown source")
