"""Learner-facing manager: lean specialists as tools; disk via Shell/Filesystem."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents import ModelSettings
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

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
from textbook_writer.runtime.workspace_tools import build_textbook_pdf_tool

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_manager_agent(
    *,
    model: str = "gpt-5.6-luna",
    book_root: str | Path,
) -> SandboxAgent[Any]:
    """Build the textbook manager bound to one chat's book directory."""

    root = Path(book_root)
    run_config = sandbox_tool_run_config(root=root)
    return SandboxAgent(
        name="Textbook manager",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto"),
            verbosity="low",
        ),
        tools=[
            build_textbook_pdf_tool(root),
            build_research_architect_agent(model=model).as_tool(
                tool_name="research-architect",
                tool_description=(
                    "Build/revise production/research.json via web search. "
                    "source_refs must be source_ids, never URLs; ≥2 hosts/topic. "
                    "Follow $research. Returns a short status only."
                ),
                max_turns=48,
                run_config=run_config,
            ),
            build_curriculum_architect_agent(model=model).as_tool(
                tool_name="curriculum-architect",
                tool_description=(
                    "Read production/research.json; write production/book-plan.json. "
                    "Returns a short status only."
                ),
                max_turns=32,
                run_config=run_config,
            ),
            build_chapter_writer_agent(model=model, book_root=root).as_tool(
                tool_name="chapter-writer",
                tool_description=(
                    "Write or revise production/chapters/<chapter_id>.json from plan slice "
                    "+ research sources, including figures via its own diagram specialist. "
                    "On QA rewrite, put every non-approve exercise_ref and notes from "
                    "verification.json into the tool input. Returns a short status only."
                ),
                max_turns=64,
                run_config=run_config,
            ),
            build_independent_verifier_agent(model=model).as_tool(
                tool_name="independent-verifier",
                tool_description=(
                    "Solve exercises without draft answers; write "
                    "production/chapters/<chapter_id>.answers.json. "
                    "Pass answer-free exercises only. Re-run after every chapter rewrite. "
                    "Returns a short status only."
                ),
                max_turns=48,
                run_config=run_config,
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
                max_turns=48,
                run_config=run_config,
            ),
        ],
        capabilities=agent_capabilities(__file__),
    )
