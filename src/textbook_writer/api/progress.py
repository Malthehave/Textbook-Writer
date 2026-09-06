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
    ManuscriptReview,
    PublicationReview,
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
    quality_passed = bool(report.get("quality_passed"))
    return {
        "status": (
            "complete"
            if within_tolerance and quality_passed
            else "needs-fit-revision"
            if not within_tolerance
            else "needs-quality-revision"
        ),
        "actual_pages": report.get("actual_pages"),
        "pdf_path": pdf_path,
        "solutions_pdf_path": report.get("solutions_pdf_path"),
        "solutions_pages": report.get("solutions_pages"),
        "minimum_pages": report.get("minimum_pages"),
        "maximum_pages": report.get("maximum_pages"),
        "within_tolerance": within_tolerance,
        "quality_passed": quality_passed,
        "quality_issues": report.get("quality_issues", []),
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
    manuscript_path = production / "manuscript.review.json"
    manuscript_review, manuscript_file_status = _load_model(
        manuscript_path, ManuscriptReview
    )
    modern_flow = plan is not None
    chapter_paths = (
        [production / "chapters" / f"{chapter.chapter_id}.json" for chapter in plan.chapters]
        if plan is not None
        else []
    )
    manuscript_fresh = bool(
        manuscript_review is not None
        and all(path.is_file() for path in chapter_paths)
        and all(_modified(manuscript_path) >= _modified(path) for path in chapter_paths)
    )
    if manuscript_file_status == "invalid":
        manuscript_status = "invalid"
    elif manuscript_review is None:
        manuscript_status = "pending"
    elif not manuscript_fresh:
        manuscript_status = "stale"
    elif modern_flow and manuscript_review.reader_experience is None:
        manuscript_status = "unscored"
    elif modern_flow and manuscript_review.reader_experience.minimum < 4:
        manuscript_status = "revise"
    else:
        manuscript_status = manuscript_review.decision

    chapters: list[dict[str, Any]] = []
    completed_milestones = int(research is not None) + int(plan is not None)
    total_milestones = 2
    if plan is not None:
        total_milestones += (
            len(plan.chapters) * 2 + 3
            if modern_flow
            else len(plan.chapters) * 3 + 3
        )
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
                if modern_flow:
                    if manuscript_status == "approve":
                        editorial = "approved"
                        stage = "editorial-approved"
                    elif manuscript_status == "revise":
                        editorial = "revise"
                        stage = "revision-requested"
                    elif manuscript_status in {"invalid", "stale"}:
                        editorial = manuscript_status
                        stage = "revised"
                    else:
                        editorial = "pending"
                    is_accepted = manuscript_status == "approve"
                review_is_fresh = (
                    review is not None
                    and review.chapter_ref == planned.chapter_id
                    and _modified(review_path) >= _modified(chapter_path)
                )
                if modern_flow:
                    pass
                elif review_file_status == "invalid":
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

    if manuscript_status == "approve":
        completed_milestones += 1

    publication = _publication_progress(production, workspace)
    if publication["status"] == "complete":
        completed_milestones += 1

    publication_review_path = production / "publication.review.json"
    publication_review, publication_review_file_status = _load_model(
        publication_review_path, PublicationReview
    )
    publication_report_path = production / "publication-report.json"
    publication_review_fresh = bool(
        publication_review is not None
        and _modified(publication_review_path) >= _modified(publication_report_path)
    )
    if publication_review_file_status == "invalid":
        publication_review_status = "invalid"
    elif publication_review is None:
        publication_review_status = "pending"
    elif not publication_review_fresh:
        publication_review_status = "stale"
    else:
        publication_review_status = publication_review.decision
        if publication_review.decision == "approve":
            completed_milestones += 1

    if publication["status"] == "complete" and publication_review_status == "approve":
        status = "published"
    elif publication["status"] in {"needs-fit-revision", "needs-quality-revision"}:
        status = "publication-revision"
    elif any(chapter["stage"] != "pending" for chapter in chapters):
        status = "writing"
    elif plan is not None:
        status = "ready-to-write"
    elif research is not None:
        status = "planning"
    else:
        status = "scoping"

    next_actions: list[str] = []
    if research is None:
        next_actions.append("research-architect")
    elif plan is None:
        next_actions.append("lead-author:complete-manuscript")
    elif modern_flow:
        missing_drafts = [chapter for chapter in chapters if chapter["draft"] != "complete"]
        missing_visuals: list[tuple[str, str]] = []
        for planned in plan.chapters:
            if planned.visual is None:
                continue
            chapter, _ = _load_model(
                production / "chapters" / f"{planned.chapter_id}.json",
                ProductChapter,
            )
            attached = {figure.figure_id for figure in chapter.figures} if chapter else set()
            if planned.visual.visual_id not in attached:
                missing_visuals.append((planned.chapter_id, planned.visual.visual_id))
        if missing_drafts:
            next_actions.append("lead-author:complete-manuscript")
        elif missing_visuals:
            chapter_id, visual_id = missing_visuals[0]
            next_actions.append(f"html-diagram-author:{chapter_id}:{visual_id}")
        elif manuscript_status == "revise":
            next_actions.append("lead-author:manuscript-revision")
        elif manuscript_status != "approve":
            next_actions.append("reader-experience-editor")
        else:
            incomplete_qa = [
                chapter for chapter in chapters if chapter["exercise_qa"] != "approved"
            ]
            if incomplete_qa:
                chapter = incomplete_qa[0]
                next_actions.append(
                    f"independent-verifier:{chapter['chapter_id']}"
                    if chapter["answers"] != "complete"
                    else f"solution-comparator:{chapter['chapter_id']}"
                )
            elif publication["status"] != "complete":
                next_actions.append("build-textbook-pdf")
            elif publication_review_status != "approve":
                next_actions.append("publication-reviewer")
    else:
        incomplete_editorial = [
            chapter for chapter in chapters if chapter["editorial"] != "approved"
        ]
        if incomplete_editorial:
            chapter = incomplete_editorial[0]
            next_actions.append(
                f"chapter-writer:{chapter['chapter_id']}"
                if chapter["stage"] in {"pending", "revision-requested"}
                else f"chapter-reviewer:{chapter['chapter_id']}"
            )
        elif manuscript_status != "approve":
            next_actions.append("chapter-reviewer:final-manuscript-pass")
        else:
            incomplete_qa = [
                chapter for chapter in chapters if chapter["exercise_qa"] != "approved"
            ]
            if incomplete_qa:
                chapter = incomplete_qa[0]
                next_actions.append(
                    f"independent-verifier:{chapter['chapter_id']}"
                    if chapter["answers"] != "complete"
                    else f"solution-comparator:{chapter['chapter_id']}"
                )
            elif publication["status"] != "complete":
                next_actions.append("build-textbook-pdf")
            elif publication_review_status != "approve":
                next_actions.append("publication-reviewer")

    return {
        "status": status,
        "research": research_status,
        "curriculum": curriculum_status,
        "editorial_state": editorial_status,
        "manuscript": manuscript_status,
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
        "publication_review": publication_review_status,
        "next_actions": next_actions,
    }
