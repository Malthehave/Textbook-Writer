"""Answer-hidden exercise solver specialist."""

from __future__ import annotations

from typing import Any

from agents.sandbox import SandboxAgent

from textbook_writer.models.product import IndependentAnswerSet
from textbook_writer.runtime.agents._shared import load_prompt, model_settings
from textbook_writer.runtime.skills_runtime import skilled_agent_capabilities

PROMPT = load_prompt(__file__)


def build_independent_verifier_agent(*, model: str) -> SandboxAgent[Any]:
    return SandboxAgent(
        name="Independent exercise solver",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(),
        output_type=IndependentAnswerSet,
        capabilities=skilled_agent_capabilities("exercise-verification"),
    )
