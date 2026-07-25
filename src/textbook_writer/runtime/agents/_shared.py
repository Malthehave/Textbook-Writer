"""Shared agent helpers: default model, settings, prompt loading."""

from __future__ import annotations

from pathlib import Path

from agents import ModelSettings
from openai.types.shared_params import Reasoning

DEFAULT_RESEARCH_MODEL = "gpt-5.6-luna"


def load_prompt(agent_file: str | Path, *, name: str = "prompt.md") -> str:
    """Load a markdown prompt sibling to an agent module."""

    path = Path(agent_file).resolve().with_name(name)
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip() + "\n"


def model_settings(*, web: bool = False, effort: str | None = None) -> ModelSettings:
    return ModelSettings(
        reasoning=Reasoning(effort=effort or ("medium" if web else "low")),
        verbosity="low",
        response_include=["web_search_call.action.sources"] if web else None,
    )
