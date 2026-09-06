"""HTML pedagogical diagram author specialist."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from agents import FunctionTool, ModelSettings, ToolOutputImage, ToolOutputText, function_tool
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

from textbook_writer.runtime.agents import agent_capabilities
from textbook_writer.runtime.agents.html_diagram_author.render import write_html_diagram
from textbook_writer.models.product import ProductChapter, ProductFigure
from textbook_writer.runtime.workspace_tools import (
    _validate_production_artifact,
    write_model,
)

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_rasterize_html_diagram_tool(book_root: Path) -> FunctionTool:
    workspace = Path(book_root)

    @function_tool(name_override="rasterize-html-diagram")
    def rasterize_html_diagram(
        figure_id: str, html: str
    ) -> list[ToolOutputText | ToolOutputImage]:
        """Rasterize self-contained diagram HTML to PNG and return the image for visual QA.

        Pass the full HTML document (with #diagram). Returns a status line plus the PNG
        so you can see clipping, crowding, and math. Fix and re-rasterize if needed.
        """

        html_rel, png_rel = write_html_diagram(
            workspace=workspace,
            figure_id=figure_id,
            html=html,
        )
        png_bytes = (workspace / png_rel).read_bytes()
        data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
        return [
            ToolOutputText(text=f"html={html_rel} png={png_rel}"),
            ToolOutputImage(image_url=data_url, detail="high"),
        ]

    return rasterize_html_diagram


def build_attach_html_diagram_tool(book_root: Path) -> FunctionTool:
    workspace = Path(book_root)

    @function_tool(name_override="attach-html-diagram")
    def attach_html_diagram(
        chapter_id: str,
        figure_id: str,
        caption: str,
        learning_purpose: str,
        section_ref: str | None,
        html_path: str,
        asset_path: str,
    ) -> str:
        """Atomically attach a rasterized diagram to a chapter and validate the result."""

        chapter_path = workspace / "production" / "chapters" / f"{chapter_id}.json"
        chapter = ProductChapter.model_validate_json(
            chapter_path.read_text(encoding="utf-8")
        )
        resolved_html = (workspace / html_path).resolve()
        resolved_asset = (workspace / asset_path).resolve()
        if not resolved_html.is_relative_to(workspace.resolve()):
            raise ValueError("html_path escapes the book workspace")
        if not resolved_asset.is_relative_to(workspace.resolve()):
            raise ValueError("asset_path escapes the book workspace")
        if not resolved_asset.is_file() or resolved_asset.suffix.lower() != ".png":
            raise ValueError("asset_path must reference an existing PNG")
        figure = ProductFigure(
            figure_id=figure_id,
            caption=caption,
            learning_purpose=learning_purpose,
            section_ref=section_ref,
            html=resolved_html.read_text(encoding="utf-8"),
            asset_path=str(resolved_asset.relative_to(workspace.resolve())),
        )
        chapter.figures = [
            existing for existing in chapter.figures if existing.figure_id != figure_id
        ] + [figure]
        write_model(chapter_path, chapter)
        _validate_production_artifact(
            workspace, f"production/chapters/{chapter_id}.json"
        )
        return f"attached={figure_id} chapter={chapter_id} png={figure.asset_path}"

    return attach_html_diagram


def build_html_diagram_agent(*, model: str, book_root: str | Path) -> SandboxAgent[Any]:
    root = Path(book_root)
    return SandboxAgent(
        name="Technical HTML diagram author",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto"),
            verbosity="low",
        ),
        tools=[
            build_rasterize_html_diagram_tool(root),
            build_attach_html_diagram_tool(root),
        ],
        capabilities=agent_capabilities(__file__),
    )
