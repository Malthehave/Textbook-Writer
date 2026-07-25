"""Exercise answer comparator specialist."""

from __future__ import annotations

from typing import Any

from agents.sandbox import SandboxAgent

from textbook_writer.models.product import ExerciseVerification
from textbook_writer.runtime.agents._shared import load_prompt, model_settings
from textbook_writer.runtime.skills_runtime import skilled_agent_capabilities

PROMPT = load_prompt(__file__)


def build_solution_comparator_agent(*, model: str) -> SandboxAgent[Any]:
    return SandboxAgent(
        name="Exercise answer comparator",
        instructions=PROMPT,
        model=model,
        model_settings=model_settings(),
        output_type=ExerciseVerification,
        capabilities=skilled_agent_capabilities("exercise-verification"),
    )
