"""One high-leverage visual review of the compiled learner artifact."""

from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agents import FunctionTool, ModelSettings, ToolOutputImage, ToolOutputText, function_tool
from agents.sandbox import SandboxAgent
from openai.types.shared_params import Reasoning

from textbook_writer.runtime.agents import agent_capabilities
from textbook_writer.runtime.workspace_tools import production_commit_tools

PROMPT = (Path(__file__).with_name("prompt.md").read_text(encoding="utf-8").strip() + "\n")


def build_render_publication_preview_tool(book_root: Path) -> FunctionTool:
    workspace = Path(book_root)

    @function_tool(name_override="render-publication-preview")
    def render_publication_preview() -> list[ToolOutputText | ToolOutputImage]:
        """Render and return every PDF page as an individual image for visual review."""

        if shutil.which("pdftoppm") is None:
            raise RuntimeError("pdftoppm is required for publication preview")
        report_path = workspace / "production" / "publication-report.json"
        import json

        report = json.loads(report_path.read_text(encoding="utf-8"))
        pdf_path = Path(report["pdf_path"])
        if not pdf_path.is_file():
            pdf_path = workspace / "build" / pdf_path.name
        preview_dir = workspace / "state" / "publication-preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        for stale in preview_dir.glob("page-*.png"):
            stale.unlink()
        prefix = preview_dir / "page"
        subprocess.run(
            ["pdftoppm", "-png", "-r", "110", str(pdf_path), str(prefix)],
            check=True,
            capture_output=True,
        )
        pages = sorted(preview_dir.glob("page-*.png"))
        if not pages:
            raise RuntimeError("publication preview rendered no pages")
        outputs: list[ToolOutputText | ToolOutputImage] = [
            ToolOutputText(text=f"pdf={pdf_path} pages={len(pages)}")
        ]
        for page_path in pages:
            data_url = "data:image/png;base64," + base64.b64encode(
                page_path.read_bytes()
            ).decode("ascii")
            outputs.append(ToolOutputImage(image_url=data_url, detail="high"))
        return outputs

    return render_publication_preview


def build_publication_reviewer_agent(*, model: str, book_root: str | Path) -> SandboxAgent[Any]:
    root = Path(book_root)
    return SandboxAgent(
        name="Compiled textbook publication reviewer",
        instructions=PROMPT,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto"),
            verbosity="medium",
        ),
        tools=[
            build_render_publication_preview_tool(root),
            *production_commit_tools(root),
        ],
        capabilities=agent_capabilities(__file__),
    )
