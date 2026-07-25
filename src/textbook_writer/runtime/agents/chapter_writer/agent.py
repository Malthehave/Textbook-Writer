"""Source-grounded chapter writer specialist."""

from __future__ import annotations

from typing import Any

from agents.sandbox import SandboxAgent

from textbook_writer.models.product import ProductChapter
from textbook_writer.runtime.agents._shared import load_prompt, model_settings
from textbook_writer.runtime.skills_runtime import skilled_agent_capabilities

PROMPT = load_prompt(__file__)


def build_chapter_writer_agent(*, model: str) -> SandboxAgent[Any]:
    return SandboxAgent(
        name="Source-grounded textbook chapter writer",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(),
        output_type=ProductChapter,
        capabilities=skilled_agent_capabilities("textbook-prose"),
    )
