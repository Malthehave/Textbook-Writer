"""Typst compile + markdown→Typst content helpers."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from md2typst import convert

CLAIM_MARKER_RE = re.compile(r"\s*\[@[a-z0-9]+(?:-[a-z0-9]+)*\]")
CONCEPT_LINK_RE = re.compile(r"\[([^\]]+)\]\(concept:[^)]+\)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def prepare_product_markdown(markdown: str) -> str:
    """Strip textbook-specific markers that are not CommonMark."""

    text = CLAIM_MARKER_RE.sub("", markdown)
    text = CONCEPT_LINK_RE.sub(r"\1", text)
    return text.strip()


def markdown_to_typst_content(markdown: str) -> tuple[str, tuple[str, ...]]:
    """Return a Typst content block and any package imports required by the body."""

    prepared = prepare_product_markdown(markdown)
    if not prepared:
        return "[]", ()
    converted = convert(prepared, parser="markdown-it")
    imports: list[str] = []
    body_lines: list[str] = []
    for line in converted.splitlines():
        if line.startswith("#import "):
            imports.append(line)
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    if not body:
        return "[]", tuple(dict.fromkeys(imports))
    return f"[\n{body}\n]", tuple(dict.fromkeys(imports))


class ProductMarkdownRenderer:
    """Accumulate Typst package imports while converting markdown fragments."""

    def __init__(self) -> None:
        self.imports: list[str] = []

    def content(self, markdown: str) -> str:
        block, found = markdown_to_typst_content(markdown)
        for item in found:
            if item not in self.imports:
                self.imports.append(item)
        return block


def compile_typst(source: str, output_path: Path, *, typst_binary: str = "typst") -> Path:
    """Compile standalone Typst source, preserving the exact source beside the PDF."""

    if shutil.which(typst_binary) is None:
        raise RuntimeError(f"Typst compiler not found: {typst_binary}")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_path = output_path.with_suffix(".typ")
    source_path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [typst_binary, "compile", str(source_path), str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Typst compilation failed:\n{result.stderr.strip()}")
    return output_path


def _plain(markdown: str) -> str:
    text = CLAIM_MARKER_RE.sub("", markdown)
    text = CONCEPT_LINK_RE.sub(r"\1", text)
    text = BOLD_RE.sub(r"\1", text)
    paragraphs = [
        " ".join(part.split())
        for part in re.split(r"\n\s*\n", text)
        if part.strip()
    ]
    return "\n\n".join(paragraphs)
