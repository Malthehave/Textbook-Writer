"""Curriculum repair specialist."""

from __future__ import annotations

from typing import Any

from agents import Agent

from textbook_writer.models.product import ProductBookPlan
from textbook_writer.runtime.agents._shared import load_prompt, model_settings

PROMPT = load_prompt(__file__)


def build_curriculum_repair_agent(*, model: str) -> Agent[Any]:
    return Agent(
        name="Constrained curriculum repair editor",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(),
        output_type=ProductBookPlan,
    )
