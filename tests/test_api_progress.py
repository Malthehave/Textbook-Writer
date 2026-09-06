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
    ManuscriptReview,
    PlannedChapter,
    ProductBookPlan,
    ProductChapter,
    ProductExercise,
    ProductSection,
    ProductSource,
    PublicationPageBudget,
    ReaderExperienceScorecard,
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
        page_budget=PublicationPageBudget(
            front_matter=1,
            chapter_prose=1,
            figures=0,
            exercises=0,
            solutions=1,
            bibliography=1,
        ),
        study_path="Read the explanation, inspect the trace, then solve the exercise.",
        implementation_project=(
            "Build a tiny bounded-queue simulator and record its queue-depth trace."
        ),
        personalization_strategy=(
            "Bridge from the experienced engineer's systems intuition to rate analysis."
        ),
        chapters=[
            PlannedChapter(
                chapter_id="ch1",
                title="See the Queue",
                purpose="Explain backpressure.",
                central_question="Why does the queue keep growing?",
                narrative_arc=(
                    "Start from an observed queue trace, explain the rate mismatch, and "
                    "finish with a diagnosis the reader can apply."
                ),
                anchor_example="A producer and consumer connected by one bounded queue.",
                builds_on="The reader can identify the producer and consumer.",
                hands_off="The reader can recognize and explain backpressure.",
                target_words=500,
                learning_outcomes=["Explain backpressure."],
                exercise_count=1,
                assessment_brief=(
                    "Diagnose a growing queue and explain the observed rate mismatch."
                ),
                personalization_brief=(
                    "Use the learner's existing producer-consumer systems intuition."
                ),
                project_milestone=(
                    "Implement one bounded queue and emit an arrival/service trace."
                ),
                practice_brief=(
                    "Diagnose one trace before changing capacity or concurrency."
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


def _quality_slice_plan() -> ProductBookPlan:
    payload = _plan().model_dump(mode="json")
    payload.update(
        iteration_mode="quality-slice",
        target_pages=9,
        implementation_project="",
        page_budget={
            "front_matter": 1,
            "chapter_prose": 5,
            "figures": 0,
            "exercises": 1,
            "solutions": 1,
            "bibliography": 1,
        },
    )
    payload["chapters"][0].update(
        target_words=1700,
        learning_outcomes=["Explain backpressure.", "Diagnose queue growth."],
        exercise_count=2,
        reader_starting_point="The reader understands producer-consumer queues.",
        conceptual_obstacle="Capacity is easily confused with sustainable throughput.",
        intuition_bridge="Queue depth is inventory created by a rate mismatch.",
        worked_example_progression="Read a trace, calculate its slope, then test a bound.",
        mechanisms_to_explain=["rate mismatch", "bounded backpressure"],
        likely_misconceptions=["A larger queue fixes overload."],
        evidence_or_demonstration="A numerical queue-depth trace and rate calculation.",
        practice_progression="Explain one trace, then diagnose a new rate pair.",
    )
    return ProductBookPlan.model_validate(payload)


def _quality_slice_chapter() -> ProductChapter:
    chapter = _chapter().model_dump(mode="json")
    chapter["learning_outcomes"] = [
        "Explain backpressure.",
        "Diagnose queue growth.",
    ]
    chapter["exercises"].append(
        {
            "exercise_id": "ex2",
            "learning_outcome": "Diagnose queue growth.",
            "exercise_type": "debugging",
            "difficulty": "intermediate",
            "prompt": "Diagnose a queue whose depth increases by three items per second.",
            "answer": "Arrival exceeds service by three items per second.",
            "reasoning": "Queue-depth slope equals the arrival/service rate difference.",
            "source_refs": ["source-1"],
        }
    )
    return ProductChapter.model_validate(chapter)


def _make_newer(path: Path, reference: Path) -> None:
    timestamp = reference.stat().st_mtime + 1
    os.utime(path, (timestamp, timestamp))


def test_progress_ignores_legacy_per_chapter_reviews_and_uses_reader_gate(
    tmp_path: Path,
) -> None:
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
    assert derive_book_progress(tmp_path)["chapters"][0]["stage"] == "drafted"

    write_model(chapter_path, _chapter())
    _make_newer(chapter_path, review_path)
    assert derive_book_progress(tmp_path)["chapters"][0]["stage"] == "drafted"

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
    assert progress["chapters"][0]["stage"] == "drafted"
    assert progress["completed_chapters"] == 0
    assert progress["milestones"] == {"completed": 4, "total": 7}
    assert progress["manuscript"] == "pending"
    assert progress["next_actions"] == ["reader-experience-editor"]


def test_quality_slice_progress_uses_lead_author_and_reader_gate(tmp_path: Path) -> None:
    production = tmp_path / "production"
    chapters = production / "chapters"
    write_model(production / "research.json", _research())
    assert derive_book_progress(tmp_path)["next_actions"] == [
        "lead-author:complete-manuscript"
    ]

    write_model(production / "book-plan.json", _quality_slice_plan())
    assert derive_book_progress(tmp_path)["next_actions"] == [
        "lead-author:complete-manuscript"
    ]

    chapter_path = chapters / "ch1.json"
    write_model(chapter_path, _quality_slice_chapter())
    assert derive_book_progress(tmp_path)["next_actions"] == [
        "reader-experience-editor"
    ]

    review_path = production / "manuscript.review.json"
    scores = ReaderExperienceScorecard(
        narrative_coherence=4,
        explanatory_depth=3,
        paragraph_flow=4,
        sentence_rhythm=4,
        concept_scaffolding=4,
        example_continuity=4,
        practice_progression=4,
        voice_consistency=4,
    )
    write_model(
        review_path,
        ManuscriptReview(
            decision="revise",
            summary="The mechanism needs one deeper worked explanation.",
            notes=[
                {
                    "chapter_ref": "ch1",
                    "category": "explanatory-depth",
                    "evidence": "The rate relationship is asserted without a calculation.",
                    "requested_change": "Add and interpret one queue-slope calculation.",
                }
            ],
            reader_experience=scores,
        ),
    )
    _make_newer(review_path, chapter_path)
    assert derive_book_progress(tmp_path)["next_actions"] == [
        "lead-author:manuscript-revision"
    ]

    approved = scores.model_copy(update={"explanatory_depth": 4})
    write_model(
        review_path,
        ManuscriptReview(
            decision="approve",
            summary="The complete chapter now teaches the mechanism clearly.",
            notes=[],
            reader_experience=approved,
        ),
    )
    _make_newer(review_path, chapter_path)
    progress = derive_book_progress(tmp_path)
    assert progress["manuscript"] == "approve"
    assert progress["next_actions"] == ["independent-verifier:ch1"]
