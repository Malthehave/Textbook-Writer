"""HTML pedagogical diagram author specialist."""

from __future__ import annotations

from typing import Any

from agents import ModelSettings
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning
from pydantic import BaseModel, Field, field_validator

from textbook_writer.runtime.agents._shared import load_prompt
from textbook_writer.runtime.skills_runtime import skilled_agent_capabilities

TECHNICAL_HTML_DIAGRAM_SKILL = "technical-html-diagram"
PROMPT = load_prompt(__file__)
TASK_PROMPT_TAIL = load_prompt(__file__, name="task_prompt.md").strip()


class HtmlDiagramAgentOutput(BaseModel):
    html: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    learning_purpose: str = Field(min_length=1)
    self_critique: str = Field(min_length=1)

    @field_validator("html")
    @classmethod
    def require_self_contained_html(cls, value: str) -> str:
        lowered = value.lower()
        if "<html" not in lowered or "</html>" not in lowered:
            raise ValueError("html must be a complete HTML document")
        if 'id="diagram"' not in lowered and "id='diagram'" not in lowered:
            raise ValueError('html must wrap the figure in id="diagram"')
        if "http://" in lowered or "https://" in lowered:
            raise ValueError("html must not reference external URLs")
        if "<script" in lowered:
            raise ValueError("html must not include JavaScript")
        return value.strip()


def build_html_diagram_agent(*, model: str) -> SandboxAgent[Any]:
    return SandboxAgent(
        name="Technical HTML diagram author",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high"),
            verbosity="low",
        ),
        output_type=HtmlDiagramAgentOutput,
        capabilities=skilled_agent_capabilities(TECHNICAL_HTML_DIAGRAM_SKILL),
    )


def build_diagram_author_prompt(
    *,
    topic: str,
    learning_purpose: str,
    caption_hint: str = "",
    running_system: str = "",
    chapter_title: str = "",
) -> str:
    parts = [
        "Author one pedagogical HTML diagram for a textbook page.\n",
        f"<topic>{topic}</topic>\n",
        f"<learning-purpose>{learning_purpose}</learning-purpose>\n",
    ]
    if caption_hint.strip():
        parts.append(f"<caption-hint>{caption_hint.strip()}</caption-hint>\n")
    if chapter_title.strip():
        parts.append(f"<chapter-title>{chapter_title.strip()}</chapter-title>\n")
    if running_system.strip():
        parts.append(f"<running-system>{running_system.strip()}</running-system>\n")
    parts.append(TASK_PROMPT_TAIL)
    return "".join(parts)
