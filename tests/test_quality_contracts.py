from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from textbook_writer.models.product import (
    BlindAnswer,
    BlindAnswers,
    ChapterReview,
    EditorialState,
    ExerciseVerdict,
    ExerciseVerification,
    GroundedClaim,
    PlannedChapter,
    PlannedVisual,
    ProductBook,
    ProductBookPlan,
    ProductChapter,
    ProductExercise,
    ProductFigure,
    ProductSection,
    ProductSource,
    Research,
    ResearchedTopic,
)
from textbook_writer.runtime.workspace_tools import (
    _assemble_book,
    _validate_production_artifact,
    artifact_contract_help,
    commit_production_artifact_tool,
    write_model,
)


def _research() -> Research:
    return Research(
        research_id="research-1",
        title="Reliable Systems",
        audience="Experienced engineers",
        learning_goal="Diagnose and improve a bounded training system.",
        sources=[
            ProductSource(
                source_id="source-1",
                title="Canonical systems guide",
                url="https://example.com/guide",
                authority="canonical",
                credibility_rationale="Primary technical documentation.",
            ),
            ProductSource(
                source_id="source-2",
                title="Production queue guide",
                url="https://docs.example.org/queues",
                authority="official",
                credibility_rationale="Official operational documentation.",
            ),
        ],
        topics=[
            ResearchedTopic(
                topic_id="topic-1",
                title="Bounded queues",
                learning_outcomes=["Explain backpressure."],
                source_refs=["source-1", "source-2"],
                claims=[
                    GroundedClaim(
                        claim_id="claim-1",
                        statement="A bounded queue makes overload visible.",
                        source_refs=["source-1"],
                    )
                ],
            )
        ],
    )


def _plan(*, exercise_count: int = 3, visual: bool = True) -> ProductBookPlan:
    return ProductBookPlan(
        plan_id="plan-1",
        title="Reliable Training Systems",
        audience="Experienced engineers",
        learning_goal="Diagnose and improve a bounded training system.",
        target_pages=12,
        running_system="A producer, bounded queue, and learner.",
        chapters=[
            PlannedChapter(
                chapter_id="chapter-1",
                title="See the Queue",
                purpose="Connect queue state to system throughput.",
                topic_refs=["topic-1"],
                learning_outcomes=[
                    "Explain backpressure.",
                    "Diagnose queue growth.",
                    "Design a bounded intervention.",
                ],
                target_words=1800,
                exercise_count=exercise_count,
                assessment_brief=(
                    "Explain the mechanism, diagnose a trace, and design a measured "
                    "intervention with explicit grading evidence."
                ),
                visual=(
                    PlannedVisual(
                        visual_id="visual-1",
                        diagram_type="queue-depth timeline",
                        learning_purpose="Relate producer and learner rates to queue growth.",
                        caption="Queue depth grows when production exceeds consumption.",
                    )
                    if visual
                    else None
                ),
            )
        ],
    )


def _exercises(count: int = 3) -> list[ProductExercise]:
    outcomes = [
        "Explain backpressure.",
        "Diagnose queue growth.",
        "Design a bounded intervention.",
    ]
    return [
        ProductExercise(
            exercise_id=f"exercise-{index + 1}",
            learning_outcome=outcomes[index],
            exercise_type=("conceptual", "debugging", "system-design")[index],
            difficulty=("introductory", "intermediate", "advanced")[index],
            prompt=f"Complete task {index + 1} using the supplied queue trace.",
            answer=f"Answer {index + 1}.",
            reasoning=f"Reasoning {index + 1}.",
            source_refs=["source-1"],
        )
        for index in range(count)
    ]


def _chapter(*, exercise_count: int = 3, visual: bool = True) -> ProductChapter:
    return ProductChapter(
        chapter_id="chapter-1",
        title="See the Queue",
        introduction="The producer and learner meet at one bounded queue.",
        learning_outcomes=[
            "Explain backpressure.",
            "Diagnose queue growth.",
            "Design a bounded intervention.",
        ],
        sections=[
            ProductSection(
                section_id="section-1",
                title="Rates create inventory",
                markdown="The queue grows when arrival rate exceeds service rate.",
                topic_refs=["topic-1"],
                source_refs=["source-1"],
            )
        ],
        figures=(
            [
                ProductFigure(
                    figure_id="visual-1",
                    caption="Queue depth grows when production exceeds consumption.",
                    learning_purpose="Relate producer and learner rates to queue growth.",
                    section_ref="section-1",
                    html="<div id=\"diagram\"></div>",
                    asset_path="assets/figures/visual-1.png",
                )
            ]
            if visual
            else []
        ),
        exercises=_exercises(exercise_count),
        summary="The queue turns a rate mismatch into observable inventory.",
    )


def _verification(count: int = 3, *, decision: str = "approve") -> ExerciseVerification:
    return ExerciseVerification(
        chapter_ref="chapter-1",
        verdicts=[
            ExerciseVerdict(
                exercise_ref=f"exercise-{index + 1}",
                result="equivalent",
                ambiguity="none",
                source_support="sufficient",
                notes="The prompt and answer agree.",
                decision=decision,
            )
            for index in range(count)
        ],
    )


def _blind_answers(count: int = 3) -> BlindAnswers:
    return BlindAnswers(
        chapter_ref="chapter-1",
        answers=[
            BlindAnswer(
                exercise_ref=f"exercise-{index + 1}",
                answer=f"Independent answer {index + 1}.",
                reasoning=f"Independent reasoning {index + 1}.",
                ambiguity="none",
                source_refs=["source-1"],
            )
            for index in range(count)
        ],
    )


def test_product_book_enforces_planned_exercises_visuals_and_approval() -> None:
    ProductBook(
        book_id="book-1",
        research=_research(),
        plan=_plan(),
        chapters=[_chapter()],
        exercise_verifications=[_verification()],
    )

    with pytest.raises(ValidationError, match="exercise count"):
        ProductBook(
            book_id="book-1",
            research=_research(),
            plan=_plan(),
            chapters=[_chapter(exercise_count=2)],
            exercise_verifications=[_verification(count=2)],
        )

    with pytest.raises(ValidationError, match="missing planned visual"):
        ProductBook(
            book_id="book-1",
            research=_research(),
            plan=_plan(),
            chapters=[_chapter(visual=False)],
            exercise_verifications=[_verification()],
        )

    with pytest.raises(ValidationError, match="not approved"):
        ProductBook(
            book_id="book-1",
            research=_research(),
            plan=_plan(),
            chapters=[_chapter()],
            exercise_verifications=[_verification(decision="revise")],
        )


def test_short_book_plan_has_proportional_scope() -> None:
    payload = _plan().model_dump(mode="json")
    payload["target_pages"] = 6
    payload["chapters"] = [
        {**payload["chapters"][0], "chapter_id": f"chapter-{index}"}
        for index in range(1, 3)
    ]
    with pytest.raises(ValidationError, match="at most 1 chapter"):
        ProductBookPlan.model_validate(payload)

    payload["chapters"] = [payload["chapters"][0]]
    payload["chapters"][0]["exercise_count"] = 4
    with pytest.raises(ValidationError, match="at most 3 exercises"):
        ProductBookPlan.model_validate(payload)


def test_assemble_requires_editorial_acceptance_and_existing_figure(tmp_path: Path) -> None:
    stages = tmp_path / "production"
    chapters = stages / "chapters"
    asset = tmp_path / "assets" / "figures" / "visual-1.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"\x89PNG\r\n\x1a\nfixture")

    write_model(stages / "research.json", _research())
    write_model(stages / "book-plan.json", _plan())
    write_model(chapters / "chapter-1.json", _chapter())
    write_model(chapters / "chapter-1.answers.json", _blind_answers())
    write_model(
        chapters / "chapter-1.review.json",
        ChapterReview(
            chapter_ref="chapter-1",
            decision="approve",
            summary="The chapter fits the cumulative book arc.",
        ),
    )
    write_model(chapters / "chapter-1.verification.json", _verification())
    write_model(
        stages / "editorial-state.json",
        EditorialState(accepted_chapter_refs=["chapter-1"]),
    )

    assert _validate_production_artifact(tmp_path, "production/research.json") == "Research"
    assert (
        _validate_production_artifact(
            tmp_path, "production/chapters/chapter-1.review.json"
        )
        == "ChapterReview"
    )
    assert (
        _validate_production_artifact(tmp_path, "production/chapters/chapter-1.json")
        == "ProductChapter"
    )
    assert (
        _validate_production_artifact(
            tmp_path, "production/chapters/chapter-1.answers.json"
        )
        == "BlindAnswers"
    )
    write_model(chapters / "chapter-1.answers.json", _chapter())
    with pytest.raises(ValidationError):
        _validate_production_artifact(
            tmp_path, "production/chapters/chapter-1.answers.json"
        )

    assembled = _assemble_book(tmp_path)
    assert assembled.chapters[0].figures[0].asset_path == "assets/figures/visual-1.png"

    asset.unlink()
    with pytest.raises(FileNotFoundError, match="figure asset missing"):
        _assemble_book(tmp_path)


def test_commit_production_artifact_self_reports_validation_errors(tmp_path: Path) -> None:
    tool = commit_production_artifact_tool(tmp_path)
    ctx = MagicMock()
    bad = asyncio.run(
        tool.on_invoke_tool(
            ctx,
            json.dumps(
                {
                    "path": "production/research.json",
                    "content": json.dumps({"title": "incomplete"}),
                }
            ),
        )
    )
    assert bad.startswith("invalid=production/research.json")
    assert "schema=Research" in bad
    assert "required fields:" in bad
    research_help = artifact_contract_help("production/research.json")
    assert "audience: string" in research_help
    assert "Working title for the eventual textbook" in research_help
    plan_help = artifact_contract_help("production/book-plan.json")
    assert "Published book title for the cover" in plan_help

    good = asyncio.run(
        tool.on_invoke_tool(
            ctx,
            json.dumps(
                {
                    "path": "production/research.json",
                    "content": _research().model_dump_json(),
                }
            ),
        )
    )
    assert good == "valid=production/research.json schema=Research"
    assert (tmp_path / "production" / "research.json").is_file()
