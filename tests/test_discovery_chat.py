from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from textbook_writer.models.discovery import (
    ChapterSketch,
    Inference,
    ProductionBrief,
)
from textbook_writer.models.enums import Confidence
from textbook_writer.runtime import workspace as workspace_mod
from textbook_writer.runtime.discovery_chat import (
    build_discovery_brief_tools,
    resolve_production_scope,
    suggest_page_band_values,
    write_production_brief,
)
from textbook_writer.runtime.workspace import initialize_workspace


def _draft_brief(*, approved: bool = False) -> ProductionBrief:
    approved_at = datetime.now(UTC) if approved else None
    return ProductionBrief(
        brief_id="brief-test",
        book_id="book-test",
        confirmed=["Learner wants training-velocity focus."],
        inferred=[
            Inference(
                statement="Audience is an experienced ML engineer.",
                rationale="Job posting seniority signals.",
                confidence=Confidence.MEDIUM,
            )
        ],
        unresolved=[],
        rejected=[],
        target_pages=48,
        page_tolerance=5,
        chapter_sketch=[
            ChapterSketch(
                chapter_id="chapter-01",
                title="Rollout loops",
                purpose="Establish the shared training system.",
            ),
            ChapterSketch(
                chapter_id="chapter-02",
                title="Throughput levers",
                purpose="Teach the main velocity bottlenecks.",
            ),
        ],
        scope_summary="A compact field guide on RL training velocity.",
        approved=approved,
        approved_at=approved_at,
    )


def test_production_brief_requires_approved_at_when_approved() -> None:
    with pytest.raises(ValidationError, match="approved_at"):
        ProductionBrief(
            brief_id="brief-bad",
            book_id="book-test",
            target_pages=40,
            chapter_sketch=[
                ChapterSketch(
                    chapter_id="chapter-01",
                    title="One",
                    purpose="Teach one idea.",
                )
            ],
            scope_summary="Too incomplete for approval metadata.",
            approved=True,
            approved_at=None,
        )


def test_suggest_page_band_scales_with_chapters() -> None:
    band = suggest_page_band_values(chapter_count=6, depth="intermediate")
    assert band["chapter_count"] == 6
    assert band["suggested_pages"] == 6 * 8 + max(4, round(48 * 0.2))
    assert band["minimum"] <= band["suggested_pages"] <= band["maximum"]


def test_resolve_production_scope_requires_approved_brief(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="approved production brief"):
        resolve_production_scope(tmp_path)

    write_production_brief(tmp_path, _draft_brief(approved=False))
    with pytest.raises(RuntimeError, match="approved production brief"):
        resolve_production_scope(tmp_path)

    write_production_brief(tmp_path, _draft_brief(approved=True))
    pages, tolerance, brief = resolve_production_scope(tmp_path)
    assert pages == 48
    assert tolerance == 5
    assert brief is not None and brief.approved


def test_initialize_workspace_has_no_kickoff_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace_mod, "BOOKS_ROOT", tmp_path / "books")
    workspace = initialize_workspace()
    assert workspace.root.name.startswith("draft-")
    assert workspace.book_id.startswith("book-")
    assert not (workspace.root / "input" / "kickoff.json").exists()


def test_discovery_brief_tools_exclude_kickoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace_mod, "BOOKS_ROOT", tmp_path / "books")
    workspace = initialize_workspace()
    names = {
        tool.name
        for tool in build_discovery_brief_tools(
            workspace=workspace.root, book_id=workspace.book_id
        )
    }
    assert "update_kickoff" not in names
    assert "read_kickoff" not in names
    assert {"approve_production_brief", "save_brief_draft"} <= names


def test_workspace_renames_to_title_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(workspace_mod, "BOOKS_ROOT", tmp_path / "books")
    workspace = initialize_workspace()
    renamed = workspace_mod.rename_workspace_to_title(
        workspace.root, "Reliable Agent Evaluation"
    )
    assert renamed.name == "reliable-agent-evaluation"
    assert renamed.is_dir()
