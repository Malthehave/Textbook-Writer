"""Derive learner-facing pipeline progress from canonical book artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from textbook_writer.models import (
    BlindAnswers,
    ChapterReview,
    EditorialState,
    ExerciseVerification,
    ProductBookPlan,
    ProductChapter,
    Research,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_model(path: Path, model: type[ModelT]) -> tuple[ModelT | None, str]:
    if not path.is_file():
        return None, "pending"
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8")), "complete"
    except (OSError, ValidationError, ValueError):
        return None, "invalid"


def _modified(path: Path) -> int:
    return path.stat().st_mtime_ns if path.is_file() else 0


def _answers_status(path: Path, chapter: ProductChapter) -> str:
    answers, status = _load_model(path, BlindAnswers)
    if answers is None:
        return status
    if answers.chapter_ref != chapter.chapter_id:
        return "invalid"
    expected = {exercise.exercise_id for exercise in chapter.exercises}
    actual = {answer.exercise_ref for answer in answers.answers}
    if actual != expected:
        return "invalid"
    if _modified(path) < _modified(path.parent / f"{chapter.chapter_id}.json"):
        return "stale"
    return "complete"


def _publication_progress(production: Path, workspace: Path) -> dict[str, Any]:
    report_path = production / "publication-report.json"
    if not report_path.is_file():
        return {"status": "pending"}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "invalid"}
    pdf_path = report.get("pdf_path")
    if not isinstance(pdf_path, str):
        return {"status": "invalid"}
    resolved_pdf = Path(pdf_path)
    if not resolved_pdf.is_absolute():
        resolved_pdf = workspace / resolved_pdf
    if not resolved_pdf.is_file():
        return {"status": "invalid"}
    within_tolerance = bool(report.get("within_tolerance"))
    return {
        "status": "complete" if within_tolerance else "needs-fit-revision",
        "actual_pages": report.get("actual_pages"),
        "minimum_pages": report.get("minimum_pages"),
        "maximum_pages": report.get("maximum_pages"),
        "within_tolerance": within_tolerance,
    }


def derive_book_progress(workspace: Path) -> dict[str, Any]:
    """Return a read-only progress snapshot inferred from existing files."""

    production = workspace / "production"
    research, research_status = _load_model(production / "research.json", Research)
    plan, curriculum_status = _load_model(
        production / "book-plan.json", ProductBookPlan
    )
    editorial_state, editorial_status = _load_model(
        production / "editorial-state.json", EditorialState
    )
    accepted = (
        set(editorial_state.accepted_chapter_refs) if editorial_state is not None else set()
    )

    chapters: list[dict[str, Any]] = []
    completed_milestones = int(research is not None) + int(plan is not None)
    total_milestones = 2
    if plan is not None:
        total_milestones += len(plan.chapters) * 3 + 1
        chapter_dir = production / "chapters"
        for index, planned in enumerate(plan.chapters, start=1):
            chapter_path = chapter_dir / f"{planned.chapter_id}.json"
            chapter, draft_status = _load_model(chapter_path, ProductChapter)
            review_path = chapter_dir / f"{planned.chapter_id}.review.json"
            review, review_file_status = _load_model(review_path, ChapterReview)
            answers_path = chapter_dir / f"{planned.chapter_id}.answers.json"
            verification_path = chapter_dir / f"{planned.chapter_id}.verification.json"
            verification, verification_file_status = _load_model(
                verification_path, ExerciseVerification
            )

            editorial = "pending"
            answers = "pending"
            exercise_qa = "pending"
            stage = "pending"
            is_accepted = planned.chapter_id in accepted

            if draft_status == "invalid":
                stage = "draft-invalid"
            elif chapter is not None:
                completed_milestones += 1
                stage = "drafted"
                answers = _answers_status(answers_path, chapter)
                review_is_fresh = (
                    review is not None
                    and review.chapter_ref == planned.chapter_id
                    and _modified(review_path) >= _modified(chapter_path)
                )
                if review_file_status == "invalid":
                    editorial = "invalid"
                    stage = "review-invalid"
                elif review is None:
                    editorial = "pending"
                elif not review_is_fresh:
                    editorial = "revised"
                    stage = "revised"
                elif review.decision == "revise":
                    editorial = "revise"
                    stage = "revision-requested"
                elif is_accepted:
                    editorial = "approved"
                    completed_milestones += 1
                    stage = "editorial-approved"
                else:
                    editorial = "awaiting-acceptance"
                    stage = "awaiting-acceptance"

                verification_is_fresh = (
                    verification is not None
                    and verification.chapter_ref == planned.chapter_id
                    and _modified(verification_path)
                    >= max(_modified(chapter_path), _modified(answers_path))
                )
                if verification_file_status == "invalid":
                    exercise_qa = "invalid"
                    stage = "verification-invalid"
                elif verification is not None and not verification_is_fresh:
                    exercise_qa = "stale"
                    if editorial == "approved":
                        stage = "awaiting-exercise-qa"
                elif verification is not None:
                    decisions = {verdict.decision for verdict in verification.verdicts}
                    if decisions == {"approve"}:
                        exercise_qa = "approved"
                        completed_milestones += 1
                        if editorial == "approved":
                            stage = "complete"
                    else:
                        exercise_qa = "revise"
                        stage = "exercise-revision"
                elif editorial == "approved":
                    stage = (
                        "awaiting-comparison"
                        if answers == "complete"
                        else "solving-exercises"
                    )

            chapters.append(
                {
                    "chapter_id": planned.chapter_id,
                    "title": planned.title,
                    "position": index,
                    "stage": stage,
                    "draft": draft_status,
                    "editorial": editorial,
                    "answers": answers,
                    "exercise_qa": exercise_qa,
                    "accepted": is_accepted,
                }
            )

    publication = _publication_progress(production, workspace)
    if publication["status"] == "complete":
        completed_milestones += 1

    if publication["status"] == "complete":
        status = "published"
    elif publication["status"] == "needs-fit-revision":
        status = "publication-revision"
    elif any(chapter["stage"] != "pending" for chapter in chapters):
        status = "writing"
    elif plan is not None:
        status = "ready-to-write"
    elif research is not None:
        status = "planning"
    else:
        status = "scoping"

    return {
        "status": status,
        "research": research_status,
        "curriculum": curriculum_status,
        "editorial_state": editorial_status,
        "chapters": chapters,
        "completed_chapters": sum(
            chapter["stage"] == "complete" for chapter in chapters
        ),
        "total_chapters": len(chapters),
        "milestones": {
            "completed": completed_milestones,
            "total": total_milestones,
        },
        "publication": publication,
    }
