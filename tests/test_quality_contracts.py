from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
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
    ManuscriptReview,
    PublicationPageBudget,
    PlannedChapter,
    PlannedVisual,
    ProductBook,
    ProductBookPlan,
    ProductChapter,
    ProductExercise,
    ProductFigure,
    ProductSection,
    ProductSource,
    ReaderExperienceScorecard,
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
from textbook_writer.runtime.pdf import build_textbook_pdf_file, render_product_book
from textbook_writer.runtime.quality import forecast_book_pages


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
        page_budget=PublicationPageBudget(
            front_matter=2,
            chapter_prose=5,
            figures=1,
            exercises=2,
            solutions=1,
            bibliography=1,
        ),
        study_path=(
            "Read the mechanism, implement the queue, inspect its trace, and then solve practice."
        ),
        implementation_project=(
            "Build a bounded training-queue simulator with metrics and one failure injection."
        ),
        personalization_strategy=(
            "Bridge from the experienced engineer's production intuition into training systems."
        ),
        running_system="A producer, bounded queue, and learner.",
        chapters=[
            PlannedChapter(
                chapter_id="chapter-1",
                title="See the Queue",
                purpose="Connect queue state to system throughput.",
                central_question="Why does a healthy producer still overload its learner?",
                narrative_arc=(
                    "Begin with a growing queue trace, derive the rate mismatch that causes "
                    "it, and use a bounded intervention to restore observable control."
                ),
                anchor_example="A producer feeding one learner through a bounded queue.",
                builds_on="The reader can identify producers, consumers, and throughput.",
                hands_off="The reader can diagnose queue growth and choose a bounded response.",
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
                personalization_brief=(
                    "Use the learner's existing experience diagnosing production queues."
                ),
                project_milestone=(
                    "Implement producer and learner rates with a bounded queue between them."
                ),
                practice_brief=(
                    "Start with a focused rate check, then diagnose a trace and design a bound."
                ),
            )
        ],
    )


def _quality_slice_plan() -> ProductBookPlan:
    payload = _plan(visual=False).model_dump(mode="json")
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
        target_words=1800,
        learning_outcomes=["Explain backpressure.", "Diagnose queue growth."],
        exercise_count=2,
        reader_starting_point="The reader already understands producer-consumer queues.",
        conceptual_obstacle="Queue capacity is often confused with sustainable throughput.",
        intuition_bridge="Treat queue depth as inventory created by a rate mismatch.",
        worked_example_progression="Observe a trace, calculate its slope, then test a bound.",
        mechanisms_to_explain=["arrival/service rate mismatch", "bounded backpressure"],
        likely_misconceptions=["A larger queue fixes overload."],
        evidence_or_demonstration="A numerical queue-depth trace and rate calculation.",
        practice_progression="Explain the trace first, then diagnose a new rate pair.",
    )
    return ProductBookPlan.model_validate(payload)


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
        answer_keys=[_blind_answers()],
        exercise_verifications=[_verification()],
    )

    with pytest.raises(ValidationError, match="exercise count"):
        ProductBook(
            book_id="book-1",
            research=_research(),
            plan=_plan(),
            chapters=[_chapter(exercise_count=2)],
            answer_keys=[_blind_answers(count=2)],
            exercise_verifications=[_verification(count=2)],
        )

    with pytest.raises(ValidationError, match="missing planned visual"):
        ProductBook(
            book_id="book-1",
            research=_research(),
            plan=_plan(),
            chapters=[_chapter(visual=False)],
            answer_keys=[_blind_answers()],
            exercise_verifications=[_verification()],
        )

    with pytest.raises(ValidationError, match="not approved"):
        ProductBook(
            book_id="book-1",
            research=_research(),
            plan=_plan(),
            chapters=[_chapter()],
            answer_keys=[_blind_answers()],
            exercise_verifications=[_verification(decision="revise")],
        )


def test_short_book_plan_has_proportional_scope() -> None:
    payload = _plan().model_dump(mode="json")
    payload["target_pages"] = 6
    payload["page_budget"] = {
        "front_matter": 1,
        "chapter_prose": 2,
        "figures": 1,
        "exercises": 1,
        "solutions": 0,
        "bibliography": 1,
    }
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


def test_plan_rejects_status_title_and_enforces_prototype_scope() -> None:
    payload = _plan().model_dump(mode="json")
    payload["title"] = "Book plan created"
    with pytest.raises(ValidationError, match="pipeline status"):
        ProductBookPlan.model_validate(payload)

    payload = _plan().model_dump(mode="json")
    payload["iteration_mode"] = "prototype"
    payload["chapters"][0]["target_words"] = 751
    with pytest.raises(ValidationError, match="at most 750 words"):
        ProductBookPlan.model_validate(payload)


def test_quality_slice_requires_a_substantial_teaching_experience() -> None:
    plan = _quality_slice_plan()
    assert plan.iteration_mode == "quality-slice"

    payload = plan.model_dump(mode="json")
    payload["chapters"][0]["target_words"] = 900
    with pytest.raises(ValidationError, match="1500 to 2200"):
        ProductBookPlan.model_validate(payload)


def test_reader_experience_approval_requires_every_score_at_least_four() -> None:
    scores = ReaderExperienceScorecard(
        narrative_coherence=4,
        explanatory_depth=4,
        paragraph_flow=4,
        sentence_rhythm=4,
        concept_scaffolding=4,
        example_continuity=4,
        practice_progression=4,
        voice_consistency=4,
    )
    ManuscriptReview(
        decision="approve",
        summary="The manuscript is ready for learners.",
        notes=[],
        reader_experience=scores,
    )
    payload = scores.model_dump()
    payload["paragraph_flow"] = 3
    with pytest.raises(ValidationError, match="at least 4"):
        ManuscriptReview(
            decision="approve",
            summary="The manuscript is ready for learners.",
            notes=[],
            reader_experience=ReaderExperienceScorecard.model_validate(payload),
        )

def test_plan_page_budget_covers_complete_artifact() -> None:
    plan = _plan().model_copy(
        update={
            "page_budget": PublicationPageBudget(
                front_matter=2,
                chapter_prose=5,
                figures=1,
                exercises=2,
                solutions=1,
                bibliography=1,
            )
        }
    )
    assert plan.page_budget is not None
    assert plan.page_budget.total == plan.target_pages


def test_chapter_and_answers_reject_publication_placeholders_and_duplication() -> None:
    payload = _chapter().model_dump(mode="json")
    payload["introduction"] = payload["sections"][0]["markdown"]
    with pytest.raises(ValidationError, match="duplicates the first section"):
        ProductChapter.model_validate(payload)

    exercise = _exercises(1)[0].model_dump(mode="json")
    exercise["answer"] = "Learner response required; no draft answer is supplied."
    with pytest.raises(ValidationError, match="placeholder"):
        ProductExercise.model_validate(exercise)


def test_render_uses_independent_answer_not_author_draft() -> None:
    book = ProductBook(
        book_id="book-1",
        research=_research(),
        plan=_plan(),
        chapters=[_chapter()],
        answer_keys=[_blind_answers()],
        exercise_verifications=[_verification()],
    )
    rendered = render_product_book(book)
    assert "Independent answer 1" in rendered
    assert "Answer 1." not in rendered


def test_quality_slice_render_omits_report_front_matter_and_uses_numbered_citations() -> None:
    chapter = _chapter(exercise_count=2, visual=False).model_copy(
        update={
            "learning_outcomes": [
                "Explain backpressure.",
                "Diagnose queue growth.",
            ]
        }
    )
    book = ProductBook(
        book_id="book-1",
        research=_research(),
        plan=_quality_slice_plan(),
        chapters=[chapter],
        answer_keys=[_blind_answers(count=2)],
        exercise_verifications=[_verification(count=2)],
    )
    rendered = render_product_book(book)
    assert "#outline(" not in rendered
    assert "How to use this book" not in rendered
    assert "Research standard" not in rendered
    assert "#link(<source-1>)[\\[1\\]]" in rendered
    assert "Sources:" not in rendered


def test_quality_slice_compiles_as_a_direct_learning_experience(tmp_path: Path) -> None:
    if shutil.which("typst") is None:
        pytest.skip("Typst is not installed")
    base = _chapter(exercise_count=2, visual=False)
    teaching_paragraphs = [
        (
            "Queue depth is inventory, so its slope reveals the rate mismatch rather than "
            "merely reporting that a queue is large. In the running trainer, thirty-six "
            "unrolls arrive each minute while twenty-five leave. The eleven-unroll "
            "difference accumulates every minute, which lets the reader predict the trace "
            "before changing capacity. That prediction matters because a larger buffer "
            "delays overload without changing either rate."
        ),
        (
            "Now follow one unroll through the same system. Its enqueue timestamp records "
            "when transport begins, its consume timestamp reveals residence time, and its "
            "behavior-policy version records which parameters selected the actions. These "
            "measurements separate operational age from policy lag: time can increase while "
            "the version stays fixed, or versions can advance while queue residence remains "
            "short. The distinction turns a vague stale-data complaint into a diagnosis."
        ),
        (
            "A bounded response follows from that diagnosis. Admission control stops the "
            "producer from creating work the learner cannot consume, while expiry gives old "
            "work an explicit disposition. Neither control makes the data on-policy; it only "
            "limits how stale accepted work may become. The algorithm still needs correction "
            "compatible with its objective, and the operator still needs return and loss "
            "signals to decide whether the remaining lag harms learning."
        ),
    ]
    chapter = base.model_copy(
        update={
            "learning_outcomes": [
                "Explain backpressure.",
                "Diagnose queue growth.",
            ],
            "sections": [
                base.sections[0].model_copy(
                    update={"markdown": "\n\n".join(teaching_paragraphs * 9)}
                )
            ],
            "exercises": [
                exercise.model_copy(
                    update={
                        "prompt": exercise.prompt
                        + " Explain the observed slope, identify the operational control "
                        "that changes accepted work, and state which measurement would "
                        "distinguish queue residence from behavior-policy lag. Justify each "
                        "step from the supplied rate relationship rather than proposing an "
                        "unmeasured capacity increase."
                    }
                )
                for exercise in base.exercises
            ],
        }
    )
    answer_keys = _blind_answers(count=2)
    answer_keys = answer_keys.model_copy(
        update={
            "answers": [
                answer.model_copy(
                    update={
                        "rubric": (
                            "A complete response calculates the queue-depth slope from the "
                            "arrival and service rates, explains why added capacity changes "
                            "delay but not sustainable throughput, proposes a bounded "
                            "admission or expiry rule, and names timestamps plus policy "
                            "versions that separate residence time from policy lag."
                        )
                    }
                )
                for answer in answer_keys.answers
            ]
        }
    )
    book = ProductBook(
        book_id="quality-slice",
        research=_research(),
        plan=_quality_slice_plan(),
        chapters=[chapter],
        answer_keys=[answer_keys],
        exercise_verifications=[_verification(count=2)],
    )
    book_path = tmp_path / "production" / "book.json"
    write_model(book_path, book)
    report = build_textbook_pdf_file(
        book_path=book_path,
        output_path=tmp_path / "build" / "quality-slice.pdf",
    )
    typst = Path(str(report["typst_path"])).read_text(encoding="utf-8")
    assert "#outline(" not in typst
    assert "How to use this book" not in typst
    assert report["blank_pages"] == []


def test_page_forecast_counts_exercises_solutions_and_figures() -> None:
    forecast = forecast_book_pages(
        plan=_plan(),
        chapters=[_chapter()],
        answer_keys=[_blind_answers()],
        source_count=2,
    )
    assert forecast["content"]["exercise_words"] > 0
    assert forecast["content"]["solution_words"] > 0
    assert forecast["content"]["figure_count"] == 1
    assert forecast["projected_pages"] >= 1


def test_separate_solution_manual_uses_verified_answers(tmp_path: Path) -> None:
    if shutil.which("typst") is None:
        pytest.skip("Typst is not installed")
    plan = _plan(visual=False).model_copy(update={"solution_mode": "separate"})
    book = ProductBook(
        book_id="book-1",
        research=_research(),
        plan=plan,
        chapters=[_chapter(visual=False)],
        answer_keys=[_blind_answers()],
        exercise_verifications=[_verification()],
    )
    book_path = tmp_path / "production" / "book.json"
    write_model(book_path, book)
    report = build_textbook_pdf_file(
        book_path=book_path, output_path=tmp_path / "build" / "book.pdf"
    )
    assert Path(str(report["pdf_path"])).is_file()
    assert Path(str(report["solutions_pdf_path"])).is_file()
    main_typst = Path(str(report["typst_path"])).read_text(encoding="utf-8")
    solutions_typst = (tmp_path / "build" / "book-solutions.typ").read_text(
        encoding="utf-8"
    )
    assert "Answer key" not in main_typst
    assert "Independent answer 1" in solutions_typst


def test_assemble_requires_reader_acceptance_and_existing_figure(tmp_path: Path) -> None:
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
        stages / "manuscript.review.json",
        ManuscriptReview(
            decision="approve",
            summary="The complete manuscript has a coherent argument and readable prose.",
            notes=[],
            reader_experience=ReaderExperienceScorecard(
                narrative_coherence=4,
                explanatory_depth=4,
                paragraph_flow=4,
                sentence_rhythm=4,
                concept_scaffolding=4,
                example_continuity=4,
                practice_progression=4,
                voice_consistency=4,
            ),
        ),
    )
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
    write_model(chapters / "chapter-1.answers.json", _blind_answers())
    write_model(chapters / "chapter-1.verification.json", _verification())

    assembled = _assemble_book(tmp_path)
    assert assembled.chapters[0].figures[0].asset_path == "assets/figures/visual-1.png"

    asset.unlink()
    with pytest.raises(FileNotFoundError, match="figure asset missing"):
        _assemble_book(tmp_path)


def test_quality_slice_assembles_without_legacy_chapter_reviews_or_editorial_state(
    tmp_path: Path,
) -> None:
    stages = tmp_path / "production"
    chapters = stages / "chapters"
    chapter = _chapter(exercise_count=2, visual=False).model_copy(
        update={
            "learning_outcomes": [
                "Explain backpressure.",
                "Diagnose queue growth.",
            ]
        }
    )
    write_model(stages / "research.json", _research())
    write_model(stages / "book-plan.json", _quality_slice_plan())
    write_model(chapters / "chapter-1.json", chapter)
    write_model(chapters / "chapter-1.answers.json", _blind_answers(count=2))
    write_model(chapters / "chapter-1.verification.json", _verification(count=2))
    write_model(
        stages / "manuscript.review.json",
        ManuscriptReview(
            decision="approve",
            summary="The complete chapter teaches a coherent mental model.",
            notes=[],
            reader_experience=ReaderExperienceScorecard(
                narrative_coherence=4,
                explanatory_depth=4,
                paragraph_flow=4,
                sentence_rhythm=4,
                concept_scaffolding=4,
                example_continuity=4,
                practice_progression=4,
                voice_consistency=4,
            ),
        ),
    )

    assembled = _assemble_book(tmp_path)
    assert assembled.plan.iteration_mode == "quality-slice"
    assert not (stages / "editorial-state.json").exists()
    assert not (chapters / "chapter-1.review.json").exists()


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
    assert "central_question" in plan_help
    assert "not a topic list" in plan_help
    manuscript_help = artifact_contract_help("production/manuscript.review.json")
    assert "notes: array[ManuscriptReviewNote]" in manuscript_help

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
