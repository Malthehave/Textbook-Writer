"""Research architect specialist."""

from __future__ import annotations

from typing import Any

from agents import Agent, WebSearchTool

from textbook_writer.models.product import ResearchDossier
from textbook_writer.runtime.agents._shared import load_prompt, model_settings

PROMPT = load_prompt(__file__)


def build_research_architect_agent(*, model: str) -> Agent[Any]:
    return Agent(
        name="Textbook research architect",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(web=True),
        tools=[WebSearchTool(search_context_size="high", external_web_access=True)],
        output_type=ResearchDossier,
    )
