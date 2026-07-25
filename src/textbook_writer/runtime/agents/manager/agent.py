"""Learner-facing manager: wires specialists and deterministic tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents import Agent, ModelSettings
from openai.types.shared_params import Reasoning

from textbook_writer.research.providers import SourceProvider
from textbook_writer.runtime.agents._shared import DEFAULT_RESEARCH_MODEL, load_prompt
from textbook_writer.runtime.agents.chapter_writer.agent import build_chapter_writer_agent
from textbook_writer.runtime.agents.continuity_editor.agent import build_continuity_editor_agent
from textbook_writer.runtime.agents.coverage_auditor.agent import build_coverage_auditor_agent
from textbook_writer.runtime.agents.curriculum_architect.agent import (
    build_curriculum_architect_agent,
)
from textbook_writer.runtime.agents.curriculum_repair.agent import build_curriculum_repair_agent
from textbook_writer.runtime.agents.exercise_repair.agent import build_exercise_repair_agent
from textbook_writer.runtime.agents.html_diagram_author.agent import build_html_diagram_agent
from textbook_writer.runtime.agents.independent_verifier.agent import (
    build_independent_verifier_agent,
)
from textbook_writer.runtime.agents.research_architect.agent import build_research_architect_agent
from textbook_writer.runtime.agents.research_auditor.agent import build_research_auditor_agent
from textbook_writer.runtime.agents.research_scout.agent import build_research_scout_agent
from textbook_writer.runtime.agents.solution_comparator.agent import (
    build_solution_comparator_agent,
)
from textbook_writer.runtime.discovery_chat import build_discovery_brief_tools
from textbook_writer.runtime.skills_runtime import as_specialist_tool
from textbook_writer.runtime.stage_persist import (
    INPUT_ARTIFACTS,
    make_artifact_input_builder,
    make_persisting_extractor,
)
from textbook_writer.runtime.workspace_tools import build_manager_workspace_tools

PROMPT = load_prompt(__file__)


def _specialist(
    agent: Any,
    *,
    workspace: Path,
    tool_name: str,
    tool_description: str,
    max_turns: int,
) -> Any:
    kwargs: dict[str, Any] = {
        "tool_name": tool_name,
        "tool_description": tool_description,
        "custom_output_extractor": make_persisting_extractor(workspace, tool_name),
        "max_turns": max_turns,
    }
    artifacts = INPUT_ARTIFACTS.get(tool_name)
    if artifacts:
        kwargs["input_builder"] = make_artifact_input_builder(workspace, *artifacts)
    return as_specialist_tool(agent, **kwargs)


def build_manager_agent(
    *,
    workspace: Path,
    book_id: str,
    model: str = DEFAULT_RESEARCH_MODEL,
    source_provider: SourceProvider | None = None,
) -> Agent[Any]:
    """Build the single textbook manager with specialists as tools + workspace tools."""

    scout = build_research_scout_agent(model=model)
    research = build_research_architect_agent(model=model)
    research_auditor = build_research_auditor_agent(model=model)
    planner = build_curriculum_architect_agent(model=model)
    coverage = build_coverage_auditor_agent(model=model)
    plan_repair = build_curriculum_repair_agent(model=model)
    writer = build_chapter_writer_agent(model=model)
    diagram = build_html_diagram_agent(model=model)
    verifier = build_independent_verifier_agent(model=model)
    comparator = build_solution_comparator_agent(model=model)
    exercise_repair = build_exercise_repair_agent(model=model)
    continuity = build_continuity_editor_agent(model=model)

    tools: list[Any] = [
        _specialist(
            scout,
            workspace=workspace,
            tool_name="research-scout",
            tool_description=(
                "Web-size the learner goal; returns compact cited leads (auto-saved). "
                "Pass a short brief."
            ),
            max_turns=12,
        ),
        _specialist(
            research,
            workspace=workspace,
            tool_name="research-architect",
            tool_description=(
                "Build a source-grounded research dossier. Auto-saves "
                "production/research-dossier.json. Pass goal, page target, URLs, scout leads."
            ),
            max_turns=16,
        ),
        _specialist(
            research_auditor,
            workspace=workspace,
            tool_name="research-auditor",
            tool_description=(
                "Audit the saved research dossier (loaded from disk). Auto-saves "
                "research-audit.json. Pass a one-line brief only."
            ),
            max_turns=12,
        ),
        _specialist(
            planner,
            workspace=workspace,
            tool_name="curriculum-architect",
            tool_description=(
                "Plan chapters from the saved dossier (loaded from disk). Auto-saves "
                "book-plan.json."
            ),
            max_turns=10,
        ),
        _specialist(
            coverage,
            workspace=workspace,
            tool_name="coverage-auditor",
            tool_description=(
                "Challenge the saved plan (loaded from disk). Auto-saves plan-audit.json. "
                "Pass a one-line brief only."
            ),
            max_turns=8,
        ),
        _specialist(
            plan_repair,
            workspace=workspace,
            tool_name="curriculum-repair",
            tool_description=(
                "Repair the saved plan using plan-audit.json (both loaded from disk). "
                "Auto-saves book-plan.json; then re-run coverage-auditor."
            ),
            max_turns=8,
        ),
        _specialist(
            writer,
            workspace=workspace,
            tool_name="chapter-writer",
            tool_description=(
                "Write one chapter with exercises. Auto-saves "
                "chapters-v1/<chapter_id>.json. Pass chapter plan slice + frozen passages."
            ),
            max_turns=12,
        ),
        _specialist(
            diagram,
            workspace=workspace,
            tool_name="html-diagram-author",
            tool_description=(
                "Author one sparse HTML diagram for a chapter visual slot. Returns HTML; "
                "merge into the chapter with save_stage_artifact."
            ),
            max_turns=8,
        ),
        _specialist(
            verifier,
            workspace=workspace,
            tool_name="independent-verifier",
            tool_description=(
                "Solve chapter exercises without seeing draft answers. Pass answer-free "
                "exercises and study material only. Ephemeral—does not save."
            ),
            max_turns=10,
        ),
        _specialist(
            comparator,
            workspace=workspace,
            tool_name="solution-comparator",
            tool_description=(
                "Compare independent solutions to the draft answer key. Auto-saves "
                "chapters-v1/<chapter_id>.verification.json."
            ),
            max_turns=8,
        ),
        _specialist(
            exercise_repair,
            workspace=workspace,
            tool_name="exercise-repair",
            tool_description=(
                "Repair rejected exercises only. Auto-saves the chapter JSON. Preserve "
                "chapter identity and approved prose."
            ),
            max_turns=8,
        ),
        _specialist(
            continuity,
            workspace=workspace,
            tool_name="continuity-editor",
            tool_description=(
                "Audit whole-book continuity. Auto-saves continuity-audit.json. "
                "Pass chapter ids / notes."
            ),
            max_turns=8,
        ),
        *build_discovery_brief_tools(workspace=workspace, book_id=book_id),
        *build_manager_workspace_tools(
            workspace=workspace,
            book_id=book_id,
            source_provider=source_provider,
        ),
    ]
    return Agent(
        name="Textbook manager",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto"),
            verbosity="low",
        ),
        tools=tools,
    )


def manager_tool_names(agent: Agent[Any]) -> list[str]:
    names: list[str] = []
    for tool in agent.tools or []:
        name = getattr(tool, "name", None) or getattr(tool, "tool_name", None)
        if name:
            names.append(str(name))
    return sorted(names)
