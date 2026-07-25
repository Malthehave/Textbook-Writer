"""Independent coverage auditor specialist."""

from __future__ import annotations

from typing import Any

from agents import Agent

from textbook_writer.models.product import PlanAudit
from textbook_writer.runtime.agents._shared import load_prompt, model_settings

PROMPT = load_prompt(__file__)


def build_coverage_auditor_agent(*, model: str) -> Agent[Any]:
    return Agent(
        name="Independent curriculum coverage auditor",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(),
        output_type=PlanAudit,
    )
