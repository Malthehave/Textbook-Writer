"""Curriculum architect specialist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents import ModelSettings
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

from textbook_writer.runtime.agents import agent_capabilities

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_curriculum_architect_agent(*, model: str) -> SandboxAgent[Any]:
    return SandboxAgent(
        name="Textbook curriculum architect",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto"),
            verbosity="low",
        ),
        capabilities=agent_capabilities(__file__),
    )
