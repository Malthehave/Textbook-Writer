"""Learner-facing manager: lean specialists as tools; disk via Shell/Filesystem."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from agents import AgentToolStreamEvent, ModelSettings, RunHooks, WebSearchTool
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

from textbook_writer.runtime.agents.chapter_reviewer.agent import build_chapter_reviewer_agent
from textbook_writer.runtime.agents.chapter_writer.agent import build_chapter_writer_agent
from textbook_writer.runtime.agents.curriculum_architect.agent import (
    build_curriculum_architect_agent,
)
from textbook_writer.runtime.agents.independent_verifier.agent import (
    build_independent_verifier_agent,
)
from textbook_writer.runtime.agents.research_architect.agent import build_research_architect_agent
from textbook_writer.runtime.agents.solution_comparator.agent import (
    build_solution_comparator_agent,
)
from textbook_writer.runtime.agents import (
    agent_capabilities,
    sandbox_tool_run_config,
)
from textbook_writer.runtime.persona import persona_section
from textbook_writer.runtime.workspace_tools import (
    build_textbook_pdf_tool,
    validate_production_artifact_tool,
)

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_manager_agent(
    *,
    model: str = "gpt-5.6-luna",
    book_root: str | Path,
    hooks: RunHooks[Any] | None = None,
    on_subagent_stream: Callable[[AgentToolStreamEvent], Any] | None = None,
    learner_persona: str | None = None,
) -> SandboxAgent[Any]:
    """Build the textbook manager bound to one chat's book directory."""

    root = Path(book_root)
    run_config = sandbox_tool_run_config(root=root)
    instructions = PROMPT
    section = persona_section(learner_persona)
    if section:
        instructions = f"{PROMPT.rstrip()}\n\n{section}"
    return SandboxAgent(
        name="Textbook manager",
        instructions=instructions,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto"),
            verbosity="low",
            parallel_tool_calls=True,
        ),
        tools=[
            WebSearchTool(),
            build_textbook_pdf_tool(root),
            validate_production_artifact_tool(root),
            build_research_architect_agent(model=model).as_tool(
                tool_name="research-architect",
                tool_description=(
                    "Build/revise production/research.json via web search. "
                    "source_refs must be source_ids, never URLs; ≥2 hosts/topic. "
                    "Follow $research. Returns a short status only."
                ),
                max_turns=24,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_curriculum_architect_agent(model=model).as_tool(
                tool_name="curriculum-architect",
                tool_description=(
                    "Read production/research.json and write a page-budgeted "
                    "production/book-plan.json. In input, pass the agreed audience, depth, "
                    "scope, target pages, and exercise expectations. Returns a short status only."
                ),
                max_turns=12,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_chapter_writer_agent(
                model=model,
                book_root=root,
                hooks=hooks,
            ).as_tool(
                tool_name="chapter-writer",
                tool_description=(
                    "Write or revise production/chapters/<chapter_id>.json from plan slice "
                    "+ research sources, including figures via its own diagram specialist. "
                    "On QA rewrite, put every non-approve exercise_ref and notes from "
                    "verification.json into the tool input. Returns a short status only."
                ),
                max_turns=24,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_chapter_reviewer_agent(model=model).as_tool(
                tool_name="chapter-reviewer",
                tool_description=(
                    "Independently review one chapter against the full plan, editorial "
                    "state, and prior accepted chapters; write "
                    "production/chapters/<chapter_id>.review.json. Pass the chapter id and "
                    "whether this is an initial review or rewrite in input. After this tool, "
                    "you MUST open the review JSON and apply the editorial gate. "
                    "Returns a short status only."
                ),
                max_turns=12,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_independent_verifier_agent(model=model).as_tool(
                tool_name="independent-verifier",
                tool_description=(
                    "Solve exercises without draft answers; write "
                    "production/chapters/<chapter_id>.answers.json. "
                    "Pass answer-free exercises only. Re-run after every chapter rewrite. "
                    "Returns a short status only."
                ),
                max_turns=12,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_solution_comparator_agent(model=model).as_tool(
                tool_name="solution-comparator",
                tool_description=(
                    "Compare answers on disk to the draft key; write "
                    "production/chapters/<chapter_id>.verification.json with concrete "
                    "notes per exercise. After this tool, you MUST open that JSON and apply "
                    "the exercise QA gate before the next chapter or publish. "
                    "Returns a short status only."
                ),
                max_turns=12,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
        ],
        capabilities=agent_capabilities(__file__),
    )
