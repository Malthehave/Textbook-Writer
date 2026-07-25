"""Whole-book continuity editor specialist."""

from __future__ import annotations

from typing import Any

from agents import Agent

from textbook_writer.models.product import ContinuityAudit
from textbook_writer.runtime.agents._shared import load_prompt, model_settings

PROMPT = load_prompt(__file__)


def build_continuity_editor_agent(*, model: str) -> Agent[Any]:
    return Agent(
        name="Whole-book continuity editor",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(),
        output_type=ContinuityAudit,
    )
