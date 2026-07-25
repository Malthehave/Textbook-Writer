"""Production-brief helpers shared by the manager agent."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents import function_tool

from textbook_writer.models.discovery import (
    ChapterSketch,
    Inference,
    ProductionBrief,
)
from textbook_writer.models.enums import Confidence

BRIEF_RELATIVE_PATH = Path("input") / "production-brief.json"


def production_brief_path(workspace: Path) -> Path:
    return workspace.resolve() / BRIEF_RELATIVE_PATH


def load_production_brief(workspace: Path) -> ProductionBrief | None:
    path = production_brief_path(workspace)
    if not path.is_file():
        return None
    return ProductionBrief.model_validate_json(path.read_text(encoding="utf-8"))


def write_production_brief(workspace: Path, brief: ProductionBrief) -> Path:
    path = production_brief_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(brief.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def default_page_tolerance(target_pages: int) -> int:
    return min(max(0, target_pages - 1), max(1, round(target_pages * 0.1)))


def suggest_page_band_values(
    *, chapter_count: int, depth: str = "intermediate"
) -> dict[str, int | str]:
    if chapter_count < 1:
        raise ValueError("chapter_count must be at least 1")
    per_chapter = {"compact": 5, "intermediate": 8, "deep": 12}.get(depth, 8)
    body = chapter_count * per_chapter
    overhead = max(4, round(body * 0.2))
    suggested = body + overhead
    tolerance = default_page_tolerance(suggested)
    return {
        "depth": depth if depth in {"compact", "intermediate", "deep"} else "intermediate",
        "chapter_count": chapter_count,
        "pages_per_chapter": per_chapter,
        "suggested_pages": suggested,
        "minimum": max(1, suggested - tolerance),
        "maximum": suggested + tolerance,
        "page_tolerance": tolerance,
    }


def resolve_production_scope(
    workspace: Path,
    *,
    page_tolerance: int | None = None,
) -> tuple[int, int, ProductionBrief]:
    """Return (target_pages, page_tolerance, approved brief)."""

    brief = load_production_brief(workspace)
    if brief is None or not brief.approved:
        raise RuntimeError(
            "production requires an approved production brief from the manager session"
        )
    tolerance = (
        brief.page_tolerance
        if brief.page_tolerance is not None
        else default_page_tolerance(brief.target_pages)
    )
    if page_tolerance is not None:
        tolerance = page_tolerance
    if tolerance < 0 or tolerance >= brief.target_pages:
        raise ValueError(
            "page tolerance must be non-negative and smaller than target pages"
        )
    return brief.target_pages, tolerance, brief


def _parse_inferences(raw: list[dict[str, str]] | None) -> list[Inference]:
    if not raw:
        return []
    items: list[Inference] = []
    for entry in raw:
        items.append(
            Inference(
                statement=entry["statement"],
                rationale=entry["rationale"],
                confidence=Confidence(entry.get("confidence", "medium")),
            )
        )
    return items


def _parse_chapter_sketch(raw: list[dict[str, str]]) -> list[ChapterSketch]:
    return [
        ChapterSketch(
            chapter_id=item["chapter_id"],
            title=item["title"],
            purpose=item["purpose"],
        )
        for item in raw
    ]


def build_discovery_brief_tools(*, workspace: Path, book_id: str) -> list[Any]:
    """Deterministic brief helpers closed over the book workspace."""

    @function_tool
    def read_production_brief() -> str:
        """Read the current production brief draft, if any."""

        brief = load_production_brief(workspace)
        if brief is None:
            return "No production brief saved yet."
        return brief.model_dump_json(indent=2)

    @function_tool
    def suggest_page_band(chapter_count: int, depth: str = "intermediate") -> str:
        """Suggest a page target from chapter count and depth (compact|intermediate|deep)."""

        return json.dumps(
            suggest_page_band_values(chapter_count=chapter_count, depth=depth)
        )

    @function_tool
    def save_brief_draft(
        scope_summary: str,
        target_pages: int,
        chapter_sketch_json: str,
        confirmed_json: str = "[]",
        inferred_json: str = "[]",
        unresolved_json: str = "[]",
        rejected_json: str = "[]",
        page_tolerance: int | None = None,
    ) -> str:
        """Save or replace the draft production brief (not yet approved).

        chapter_sketch_json: JSON list of {chapter_id, title, purpose}.
        confirmed_json / inferred_json / unresolved_json / rejected_json: JSON lists.
        inferred items are {statement, rationale, confidence}.
        """

        chapters = _parse_chapter_sketch(json.loads(chapter_sketch_json))
        confirmed = list(json.loads(confirmed_json))
        inferred = _parse_inferences(json.loads(inferred_json))
        unresolved = list(json.loads(unresolved_json))
        rejected = list(json.loads(rejected_json))
        existing = load_production_brief(workspace)
        brief_id = existing.brief_id if existing is not None else "brief-production"
        brief = ProductionBrief(
            brief_id=brief_id,
            book_id=book_id,
            confirmed=confirmed,
            inferred=inferred,
            unresolved=unresolved,
            rejected=rejected,
            target_pages=target_pages,
            page_tolerance=page_tolerance,
            chapter_sketch=chapters,
            scope_summary=scope_summary,
            approved=False,
            approved_at=None,
        )
        path = write_production_brief(workspace, brief)
        return (
            f"Saved draft brief at {path} "
            f"({len(chapters)} chapters, {target_pages} pages)."
        )

    @function_tool
    def approve_production_brief() -> str:
        """Mark the saved draft brief approved after the learner explicitly confirms."""

        brief = load_production_brief(workspace)
        if brief is None:
            return "Cannot approve: no draft brief. Call save_brief_draft first."
        if brief.approved:
            return f"Brief already approved at {brief.approved_at.isoformat()}."
        tolerance = (
            brief.page_tolerance
            if brief.page_tolerance is not None
            else default_page_tolerance(brief.target_pages)
        )
        approved = brief.model_copy(
            update={
                "approved": True,
                "approved_at": datetime.now(UTC),
                "page_tolerance": tolerance,
            }
        )
        path = write_production_brief(workspace, approved)
        return (
            f"Approved brief at {path}: {approved.target_pages} pages "
            f"(±{tolerance}), {len(approved.chapter_sketch)} chapters."
        )

    return [
        read_production_brief,
        suggest_page_band,
        save_brief_draft,
        approve_production_brief,
    ]
