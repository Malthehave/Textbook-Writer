"""Independent reader-experience editor for the complete manuscript."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents import ModelSettings
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

from textbook_writer.runtime.agents import agent_capabilities
from textbook_writer.runtime.workspace_tools import production_commit_tools

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_chapter_reviewer_agent(
    *,
    model: str,
    book_root: str | Path,
) -> SandboxAgent[Any]:
    root = Path(book_root)
    return SandboxAgent(
        name="Reader-experience editor",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto"),
            verbosity="medium",
        ),
        tools=production_commit_tools(root),
        capabilities=agent_capabilities(__file__),
    )
