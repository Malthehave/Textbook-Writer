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
from textbook_writer.runtime.agents.independent_verifier.agent import (
    build_independent_verifier_agent,
)
from textbook_writer.runtime.agents.html_diagram_author.agent import build_html_diagram_agent
from textbook_writer.runtime.agents.research_architect.agent import build_research_architect_agent
from textbook_writer.runtime.agents.publication_reviewer.agent import (
    build_publication_reviewer_agent,
)
from textbook_writer.runtime.agents.solution_comparator.agent import (
    build_solution_comparator_agent,
)
from textbook_writer.runtime.agents import (
    agent_capabilities,
    sandbox_tool_run_config,
)
from textbook_writer.runtime.model_registry import DEFAULT_MODEL
from textbook_writer.runtime.persona import persona_section
from textbook_writer.runtime.model_routing import PipelineModels
from textbook_writer.runtime.workspace_tools import (
    build_textbook_pdf_tool,
    forecast_textbook_pages_tool,
    inspect_pipeline_state_tool,
    validate_production_artifact_tool,
)

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_manager_agent(
    *,
    model: str = DEFAULT_MODEL,
    book_root: str | Path,
    hooks: RunHooks[Any] | None = None,
    on_subagent_stream: Callable[[AgentToolStreamEvent], Any] | None = None,
    learner_persona: str | None = None,
) -> SandboxAgent[Any]:
    """Build the textbook manager bound to one chat's book directory."""

    root = Path(book_root)
    models = PipelineModels.from_base(model)
    run_config = sandbox_tool_run_config(root=root)
    instructions = PROMPT
    section = persona_section(learner_persona)
    if section:
        instructions = f"{PROMPT.rstrip()}\n\n{section}"
    return SandboxAgent(
        name="Textbook manager",
        instructions=instructions,
        model=models.manager,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto"),
            verbosity="low",
            parallel_tool_calls=True,
        ),
        tools=[
            WebSearchTool(),
            build_textbook_pdf_tool(root),
            forecast_textbook_pages_tool(root),
            inspect_pipeline_state_tool(root),
            validate_production_artifact_tool(root),
            build_research_architect_agent(model=models.research, book_root=root).as_tool(
                tool_name="research-architect",
                tool_description=(
                    "Build/revise production/research.json via web search. "
                    "The specialist commits and self-validates before returning. "
                    "source_refs must be source_ids, never URLs; ≥2 hosts/topic. "
                    "Follow $research. Returns a short status / path."
                ),
                max_turns=10,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_chapter_writer_agent(
                model=models.writer,
                book_root=root,
                hooks=hooks,
            ).as_tool(
                tool_name="lead-author",
                tool_description=(
                    "Own learning architecture and prose in one run. For a new manuscript, "
                    "read research plus the complete learner brief and commit book-plan.json "
                    "and every planned chapter. Prefer a quality-slice (8–10 pages, one "
                    "1500–2200 word chapter) for iteration. For revision, pass the canonical "
                    "manuscript review, verification, or publication report path. The manager "
                    "attaches planned figures separately. Returns committed paths only."
                ),
                max_turns=18,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_html_diagram_agent(model=models.diagram, book_root=root).as_tool(
                tool_name="html-diagram-author",
                tool_description=(
                    "Render and atomically attach one planned figure to an already drafted "
                    "chapter. Pass chapter id, visual id, learning purpose, caption, and "
                    "target section. This call is independent from chapter prose authoring."
                ),
                max_turns=8,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_chapter_reviewer_agent(model=models.reviewer, book_root=root).as_tool(
                tool_name="reader-experience-editor",
                tool_description=(
                    "Read the complete learner-visible manuscript in order and write "
                    "production/manuscript.review.json with an eight-dimension reader "
                    "experience scorecard and executable evidence-backed notes. Approval "
                    "requires every score >=4. Returns path, decision, minimum score, and "
                    "note count."
                ),
                max_turns=6,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_independent_verifier_agent(model=models.solver, book_root=root).as_tool(
                tool_name="independent-verifier",
                tool_description=(
                    "Solve exercises without draft answers; write "
                    "production/chapters/<chapter_id>.answers.json after self-validating. "
                    "Pass answer-free exercises only. Re-run after every chapter rewrite. "
                    "Returns a short status / path."
                ),
                max_turns=6,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_solution_comparator_agent(model=models.comparator, book_root=root).as_tool(
                tool_name="solution-comparator",
                tool_description=(
                    "Compare answers on disk to the draft key; write "
                    "production/chapters/<chapter_id>.verification.json after "
                    "self-validating, with concrete notes per exercise. After this tool, "
                    "you MUST open that JSON and apply the exercise QA gate before the "
                    "next chapter or publish. Returns a short status / path."
                ),
                max_turns=6,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
            build_publication_reviewer_agent(
                model=models.publication_reviewer, book_root=root
            ).as_tool(
                tool_name="publication-reviewer",
                tool_description=(
                    "After a successful compile, visually inspect every PDF page and write "
                    "production/publication.review.json. Use once per compiled revision; "
                    "apply only material learner-visible issues."
                ),
                max_turns=6,
                run_config=run_config,
                hooks=hooks,
                on_stream=on_subagent_stream,
            ),
        ],
        capabilities=agent_capabilities(__file__),
    )
