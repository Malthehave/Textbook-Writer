from __future__ import annotations

import json
import os
from pathlib import Path

from textbook_writer.api.progress import derive_book_progress
from textbook_writer.models.product import (
    ChapterReview,
    EditorialState,
    ExerciseVerdict,
    ExerciseVerification,
    GroundedClaim,
    PlannedChapter,
    ProductBookPlan,
    ProductChapter,
    ProductExercise,
    ProductSection,
    ProductSource,
    Research,
    ResearchedTopic,
)
from textbook_writer.runtime.workspace_tools import write_model


def _research() -> Research:
    return Research(
        research_id="research-1",
        title="Queues",
        audience="Engineers",
        learning_goal="Understand bounded queues.",
        sources=[
            ProductSource(
                source_id="source-1",
                title="Queue guide",
                url="https://example.com/queues",
                authority="canonical",
                credibility_rationale="Primary documentation.",
            ),
            ProductSource(
                source_id="source-2",
                title="Operational queue guide",
                url="https://docs.example.org/queues",
                authority="official",
                credibility_rationale="Official operational documentation.",
            ),
        ],
        topics=[
            ResearchedTopic(
                topic_id="topic-1",
                title="Backpressure",
                learning_outcomes=["Explain backpressure."],
                source_refs=["source-1", "source-2"],
                claims=[
                    GroundedClaim(
                        claim_id="claim-1",
                        statement="Bounded queues expose overload.",
                        source_refs=["source-1"],
                    )
                ],
            )
        ],
    )


def _plan() -> ProductBookPlan:
    return ProductBookPlan(
        plan_id="plan-1",
        title="Queues",
        audience="Engineers",
        learning_goal="Understand bounded queues.",
        target_pages=4,
        chapters=[
            PlannedChapter(
                chapter_id="ch1",
                title="See the Queue",
                purpose="Explain backpressure.",
                target_words=500,
                learning_outcomes=["Explain backpressure."],
                exercise_count=1,
                assessment_brief=(
                    "Diagnose a growing queue and explain the observed rate mismatch."
                ),
                topic_refs=["topic-1"],
            )
        ],
    )


def _chapter() -> ProductChapter:
    return ProductChapter(
        chapter_id="ch1",
        title="See the Queue",
        introduction="A queue connects producers and consumers.",
        learning_outcomes=["Explain backpressure."],
        sections=[
            ProductSection(
                section_id="s1",
                title="Rates",
                markdown="The queue grows when arrivals exceed service.",
                topic_refs=["topic-1"],
                source_refs=["source-1"],
            )
        ],
        exercises=[
            ProductExercise(
                exercise_id="ex1",
                learning_outcome="Explain backpressure.",
                exercise_type="conceptual",
                difficulty="introductory",
                prompt="Why does the queue grow?",
                answer="Arrivals exceed service.",
                reasoning="Inventory accumulates.",
                source_refs=["source-1"],
            )
        ],
        summary="Queue depth exposes a rate mismatch.",
    )


def _make_newer(path: Path, reference: Path) -> None:
    timestamp = reference.stat().st_mtime + 1
    os.utime(path, (timestamp, timestamp))


def test_progress_follows_artifact_state_and_freshness(tmp_path: Path) -> None:
    production = tmp_path / "production"
    chapters = production / "chapters"
    write_model(production / "research.json", _research())
    write_model(production / "book-plan.json", _plan())

    progress = derive_book_progress(tmp_path)
    assert progress["status"] == "ready-to-write"
    assert progress["chapters"][0]["stage"] == "pending"

    chapter_path = chapters / "ch1.json"
    review_path = chapters / "ch1.review.json"
    write_model(chapter_path, _chapter())
    write_model(
        review_path,
        ChapterReview(
            chapter_ref="ch1",
            decision="revise",
            summary="Clarify the rate mismatch.",
            notes=[
                {
                    "category": "pedagogy",
                    "evidence": "The rate boundary is implicit.",
                    "requested_change": "Name both rates.",
                }
            ],
        ),
    )
    _make_newer(review_path, chapter_path)
    assert derive_book_progress(tmp_path)["chapters"][0]["stage"] == (
        "revision-requested"
    )

    write_model(chapter_path, _chapter())
    _make_newer(chapter_path, review_path)
    assert derive_book_progress(tmp_path)["chapters"][0]["stage"] == "revised"

    write_model(
        review_path,
        ChapterReview(
            chapter_ref="ch1",
            decision="approve",
            summary="The chapter is coherent.",
        ),
    )
    _make_newer(review_path, chapter_path)
    write_model(
        production / "editorial-state.json",
        EditorialState(accepted_chapter_refs=["ch1"]),
    )
    answers_path = chapters / "ch1.answers.json"
    answers_path.write_text(
        json.dumps(
            {
                "chapter_ref": "ch1",
                "answers": [
                    {
                        "exercise_ref": "ex1",
                        "answer": "Arrivals exceed service.",
                        "reasoning": "Inventory accumulates.",
                        "ambiguity": "none",
                        "source_refs": ["source-1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _make_newer(answers_path, chapter_path)
    verification_path = chapters / "ch1.verification.json"
    write_model(
        verification_path,
        ExerciseVerification(
            chapter_ref="ch1",
            verdicts=[
                ExerciseVerdict(
                    exercise_ref="ex1",
                    result="equivalent",
                    ambiguity="none",
                    source_support="sufficient",
                    notes="The answer matches.",
                    decision="approve",
                )
            ],
        ),
    )
    _make_newer(verification_path, answers_path)

    progress = derive_book_progress(tmp_path)
    assert progress["chapters"][0]["stage"] == "complete"
    assert progress["completed_chapters"] == 1
    assert progress["milestones"] == {"completed": 5, "total": 6}
