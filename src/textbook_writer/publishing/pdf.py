"""Read-only PDF release inspection."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import Field
from pypdf import PdfReader

from textbook_writer.models.base import Model


class PdfInspection(Model):
    pages: int = Field(ge=1)
    internal_links: int = Field(ge=0)
    external_links: int = Field(ge=0)
    outline_entries: int = Field(ge=0)
    blank_pages: list[int] = Field(default_factory=list)
    broken_links: list[str] = Field(default_factory=list)
    extracted_text: str


def inspect_pdf(path: Path) -> PdfInspection:
    path = path.resolve()
    reader = PdfReader(path)
    internal_links = 0
    external_links = 0
    broken_links: list[str] = []
    named_destinations = reader.named_destinations
    for page in reader.pages:
        annotations = page.get("/Annots", [])
        for annotation_ref in annotations:
            annotation = annotation_ref.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue
            action = annotation.get("/A")
            if action and action.get("/URI"):
                external_links += 1
            elif (destination := annotation.get("/Dest")) is not None or action is not None:
                internal_links += 1
                if isinstance(destination, str) and destination not in named_destinations:
                    broken_links.append(destination)
                elif destination is not None and not isinstance(destination, str):
                    try:
                        destination.get_object()
                    except (AttributeError, KeyError, TypeError, ValueError) as exc:
                        broken_links.append(f"unresolvable-direct-destination:{exc}")
    text_result = subprocess.run(
        ["pdftotext", str(path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if text_result.returncode != 0:
        raise RuntimeError(f"PDF text extraction failed: {text_result.stderr.strip()}")
    return PdfInspection(
        pages=len(reader.pages),
        internal_links=internal_links,
        external_links=external_links,
        outline_entries=_count_outline(reader.outline),
        blank_pages=[
            index
            for index, page in enumerate(reader.pages, start=1)
            if not (page.extract_text() or "").strip()
        ],
        broken_links=broken_links,
        extracted_text=text_result.stdout,
    )


def render_pdf_pages(path: Path, output_dir: Path, *, dpi: int = 120) -> list[Path]:
    """Render every PDF page to a deterministic PNG sequence for visual QA."""

    if dpi < 72 or dpi > 300:
        raise ValueError("page-render DPI must be from 72 to 300")
    path = path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / path.stem
    for prior_page in output_dir.glob(f"{path.stem}-*.png"):
        prior_page.unlink()
    result = subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(path), str(prefix)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PDF page rendering failed: {result.stderr.strip()}")
    pages = sorted(
        output_dir.glob(f"{path.stem}-*.png"),
        key=lambda item: int(item.stem.rsplit("-", 1)[1]),
    )
    expected = len(PdfReader(path).pages)
    if len(pages) != expected:
        raise RuntimeError(f"rendered {len(pages)} page images for a {expected}-page PDF")
    return pages


def _count_outline(items: list) -> int:
    count = 0
    for item in items:
        if isinstance(item, list):
            count += _count_outline(item)
        else:
            count += 1
    return count
