"""Source-grounded chapter writer specialist (owns diagram authoring)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents import ModelSettings
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

from textbook_writer.runtime.agents.html_diagram_author.agent import build_html_diagram_agent
from textbook_writer.runtime.agents import (
    agent_capabilities,
    sandbox_tool_run_config,
)

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_chapter_writer_agent(*, model: str, book_root: str | Path) -> SandboxAgent[Any]:
    root = Path(book_root)
    run_config = sandbox_tool_run_config(root=root)
    return SandboxAgent(
        name="Source-grounded textbook chapter writer",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="low"),
            verbosity="low",
        ),
        tools=[
            build_html_diagram_agent(model=model, book_root=root).as_tool(
                tool_name="html-diagram-author",
                tool_description=(
                    "Author one HTML diagram for this chapter and merge it into the chapter "
                    "JSON on disk. Call after the chapter draft exists. Returns a short status."
                ),
                max_turns=32,
                run_config=run_config,
            ),
        ],
        capabilities=agent_capabilities(__file__),
    )
