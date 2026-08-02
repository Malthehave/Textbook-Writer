"""Interview agent that authors the durable learner persona."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents import ModelSettings, WebSearchTool
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

from textbook_writer.runtime.agents import agent_capabilities
from textbook_writer.runtime.persona import persona_dir

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_persona_interviewer_agent(*, model: str = "gpt-5.6-luna") -> SandboxAgent[Any]:
    persona_dir()
    return SandboxAgent(
        name="Learner persona interviewer",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto"),
            verbosity="low",
            response_include=["web_search_call.action.sources"],
        ),
        tools=[WebSearchTool(search_context_size="medium", external_web_access=True)],
        capabilities=agent_capabilities(__file__),
    )
