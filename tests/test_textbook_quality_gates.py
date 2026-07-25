from __future__ import annotations

import pytest

from textbook_writer.models.product import (
    PlannedChapter,
    PlannedVisual,
    ProductBookPlan,
    ProductChapter,
    ProductExercise,
    ProductSection,
    RunningSystemComponent,
)
from textbook_writer.models.product import ProductFigure
from textbook_writer.runtime.quality import (
    default_glossary as _default_glossary,
    ensure_chapter_bridges as _ensure_chapter_bridges,
    ensure_plan_visuals as _ensure_plan_visuals,
    sanitize_plain_english_title as _sanitize_plain_english_title,
    validate_chapter_content as _validate_chapter_content,
)
from textbook_writer.models.product import (
    GroundedClaim,
    ProductSource,
    ResearchDossier,
    ResearchedTopic,
)


def _dossier() -> ResearchDossier:
    return ResearchDossier(
        dossier_id="dossier-quality",
        title="Reliable Agent Evaluation",
        audience="Experienced ML engineers",
        learning_goal="Design a reliable agent evaluation system.",
        sources=[
            ProductSource(
                source_id="source-official",
                title="Official evaluation guide",
                url="https://example.com/evaluation-guide",
                authority="official",
                credibility_rationale="Official implementation guidance.",
                publication_year=2026,
            ),
            ProductSource(
                source_id="source-primary",
                title="Primary evaluation study",
                url="https://example.org/evaluation-study",
                authority="primary",
                credibility_rationale="Primary empirical research.",
                publication_year=2025,
            ),
        ],
        topics=[
            ResearchedTopic(
                topic_id="topic-validity",
                title="Evaluation validity",
                why_required="Invalid graders make every downstream comparison unreliable.",
                real_world_use="Used as a production release gate for tool-using agents.",
                learning_outcomes=["Design and audit a valid outcome grader."],
                source_refs=["source-official", "source-primary"],
                practice_source_refs=["source-official"],
                claims=[
                    GroundedClaim(
                        claim_id="claim-outcomes",
                        statement="Outcome checks should match the intended task state.",
                        source_refs=["source-official", "source-primary"],
                    )
                ],
                teaching_brief=(
                    "Teach the learner to define the target construct, build state-based checks, "
                    "calibrate the grader on accepted and rejected trajectories, and inspect slice "
                    "errors before using the score for a release decision."
                ),
            )
        ],
    )


def _plan() -> ProductBookPlan:
    return ProductBookPlan(
        plan_id="plan-quality",
        title="Reliable Agent Evaluation",
        audience="Experienced ML engineers",
        learning_goal="Design a reliable agent evaluation system.",
        target_pages=7,
        running_system="A shared evaluation harness with contracts, graders, and release gates.",
        chapters=[
            PlannedChapter(
                chapter_id="chapter-validity",
                title="Build a Valid Evaluation",
                purpose="Turn intended behavior into a trustworthy release signal.",
                topic_refs=["topic-validity"],
                learning_outcomes=["Design and audit a valid outcome grader."],
                target_words=250,
                exercise_count=1,
                visual=PlannedVisual(
                    visual_id="visual-chapter-validity",
                    diagram_type="process-flow",
                    learning_purpose="Show contract to release gate.",
                    caption="Evaluation harness flow",
                ),
            )
        ],
    )


def _chapter() -> ProductChapter:
    return ProductChapter(
        chapter_id="chapter-validity",
        title="Build a Valid Evaluation",
        introduction=(
            "A production evaluation is a measurement system rather than a bag of prompts.\n\n"
            "The evaluator must define the intended outcome and show that its grader separates "
            "real success from plausible-looking failure."
        ),
        learning_outcomes=["Design and audit a valid outcome grader."],
        sections=[
            ProductSection(
                section_id="section-contract",
                title="From intent to observable state",
                markdown=(
                    "Start by writing the task contract. Figure fig-chapter-validity shows the "
                    "contract flowing into the grader and release gate in the shared harness. "
                    "Calibrate every grader against accepted, rejected, and adversarial "
                    "trajectories before trusting an aggregate score."
                ),
                topic_refs=["topic-validity"],
                source_refs=["source-official", "source-primary"],
            )
        ],
        figures=[
            ProductFigure(
                figure_id="fig-chapter-validity",
                caption="Evaluation harness: contract to release gate",
                learning_purpose="Show how a task contract flows into a release gate.",
                section_ref="section-contract",
                html="<div class='diagram'>contract → grader → gate</div>",
                asset_path="production/figures/fig-chapter-validity.png",
                content_sha256=(
                    "sha256:0123456789abcdef0123456789abcdef"
                    "0123456789abcdef0123456789abcdef"
                ),
            )
        ],
        summary=(
            "A valid evaluation defines its construct, checks real outcomes, and validates "
            "the grader before the score is used for a release decision."
        ),
        exercises=[
            ProductExercise(
                exercise_id="exercise-grader",
                learning_outcome="Design and audit a valid outcome grader.",
                exercise_type="applied",
                difficulty="intermediate",
                prompt="Design a grader for an agent that must update one database row.",
                answer="Snapshot the database, run the agent, assert the target row, and diff others.",
                reasoning="Target assertion checks success; full diff detects side effects.",
                source_refs=["source-official", "source-primary"],
            )
        ],
    )


def test_sanitize_strips_cjk_from_titles() -> None:
    assert "速度" not in _sanitize_plain_english_title("The RL Training-速度 Loop")
    assert "Loop" in _sanitize_plain_english_title("The RL Training-速度 Loop")


def test_ensure_plan_visuals_adds_glossary_and_sanitizes_titles() -> None:
    plan = _plan().model_copy(
        update={
            "title": "Velocity-速度 Guide",
            "running_system": "Rollout worker, reward service, learner, and checkpoint path",
            "chapters": [
                _plan().chapters[0].model_copy(
                    update={"title": "Build a Valid-评估 Evaluation"}
                )
            ],
        }
    )
    finalized = _ensure_plan_visuals(plan)
    assert "速度" not in finalized.title
    assert "评估" not in finalized.chapters[0].title
    assert finalized.glossary
    assert finalized.chapters[0].visual is not None


def test_default_glossary_uses_running_system_parts() -> None:
    glossary = _default_glossary(
        "Rollout worker, learner, and telemetry plane",
        _plan().chapters,
    )
    assert len(glossary) >= 2
    assert all(isinstance(item, RunningSystemComponent) for item in glossary)


def test_bridges_are_synthesized_for_later_chapters() -> None:
    first = _chapter()
    second = _chapter().model_copy(
        update={
            "chapter_id": "chapter-two",
            "title": "Scale the Evaluation",
            "bridge_from_previous": "",
        }
    )
    plan = ProductBookPlan(
        plan_id="plan-bridge",
        title="Eval",
        audience="Engineers",
        learning_goal="Build reliable evaluation.",
        target_pages=10,
        running_system="Harness and grader",
        chapters=[
            _plan().chapters[0],
            _plan().chapters[0].model_copy(
                update={
                    "chapter_id": "chapter-two",
                    "title": "Scale the Evaluation",
                    "purpose": "Distribute the harness across ranks.",
                }
            ),
        ],
    )
    ensured = _ensure_chapter_bridges(plan, [first, second])
    assert ensured[0].bridge_from_previous == ""
    assert "already" in ensured[1].bridge_from_previous.casefold()


def test_validate_rejects_meta_headers() -> None:
    chapter = _chapter()
    dirty = chapter.model_copy(
        update={
            "sections": [
                chapter.sections[0].model_copy(
                    update={
                        "markdown": (
                            "**Topics:** validity\n\n"
                            + chapter.sections[0].markdown
                        )
                    }
                )
            ]
        }
    )
    with pytest.raises(RuntimeError, match="scaffolding"):
        _validate_chapter_content(_plan().chapters[0], _dossier(), dirty)
