"""Answer-hidden exercise solver specialist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents import ModelSettings
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

from textbook_writer.runtime.agents import agent_capabilities

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_independent_verifier_agent(*, model: str) -> SandboxAgent[Any]:
    return SandboxAgent(
        name="Independent exercise solver",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="low"),
            verbosity="low",
        ),
        capabilities=agent_capabilities(__file__),
    )
