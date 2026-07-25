"""Localized exercise repair specialist."""

from __future__ import annotations

from typing import Any

from agents import Agent

from textbook_writer.models.product import ProductChapter
from textbook_writer.runtime.agents._shared import load_prompt, model_settings

PROMPT = load_prompt(__file__)


def build_exercise_repair_agent(*, model: str) -> Agent[Any]:
    return Agent(
        name="Localized exercise repair editor",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(),
        output_type=ProductChapter,
    )
