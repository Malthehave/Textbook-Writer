"""Research scout specialist with hosted web search."""

from __future__ import annotations

from agents import Agent, ModelSettings, WebSearchTool
from openai.types.shared_params import Reasoning

from textbook_writer.models.research import ResearchScoutOutput
from textbook_writer.runtime.agents._shared import DEFAULT_RESEARCH_MODEL, load_prompt

PROMPT = load_prompt(__file__)


def build_research_scout_agent(
    *,
    model: str = DEFAULT_RESEARCH_MODEL,
    additional_instructions: str | None = None,
) -> Agent[None]:
    instructions = (
        PROMPT if additional_instructions is None else f"{PROMPT}\n{additional_instructions}"
    )
    return Agent(
        name="Textbook research scout",
        instructions=instructions,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium"),
            verbosity="low",
            response_include=["web_search_call.action.sources"],
        ),
        tools=[
            WebSearchTool(
                search_context_size="high",
                external_web_access=True,
            )
        ],
        output_type=ResearchScoutOutput,
    )
