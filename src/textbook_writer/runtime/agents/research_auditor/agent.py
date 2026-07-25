"""Independent research auditor specialist."""

from __future__ import annotations

from typing import Any

from agents import Agent, WebSearchTool

from textbook_writer.models.product import ResearchAudit
from textbook_writer.runtime.agents._shared import load_prompt, model_settings

PROMPT = load_prompt(__file__)


def build_research_auditor_agent(*, model: str) -> Agent[Any]:
    return Agent(
        name="Independent curriculum research auditor",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(web=True),
        tools=[WebSearchTool(search_context_size="high", external_web_access=True)],
        output_type=ResearchAudit,
    )
