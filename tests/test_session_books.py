from __future__ import annotations

import json
from pathlib import Path

import pytest

import textbook_writer.runtime.agents as agents_runtime
from textbook_writer.api.store import find_pdf, list_artifacts
from textbook_writer.runtime.agents import create_session_book, session_book_root


def test_create_session_book_is_empty_and_keeps_siblings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agents_runtime, "BOOKS_ROOT", tmp_path)

    first = create_session_book("session-aaaaaaaaaa")
    (first / "production" / "research.json").write_text("{}", encoding="utf-8")

    second = create_session_book("session-bbbbbbbbbb")
    assert second.is_dir()
    assert (first / "production" / "research.json").is_file()
    assert not any(second.rglob("*.json"))
    assert {path.name for path in second.iterdir()} == {
        "input",
        "state",
        "build",
        "production",
    }


def test_session_book_root_rejects_bad_ids() -> None:
    with pytest.raises(ValueError):
        session_book_root("../etc")
    with pytest.raises(ValueError):
        session_book_root("session-short")


def test_find_pdf_prefers_reported_book_over_solutions(tmp_path: Path) -> None:
    build = tmp_path / "build"
    production = tmp_path / "production"
    build.mkdir()
    production.mkdir()
    book = build / "async-rl.pdf"
    solutions = build / "async-rl-solutions.pdf"
    book.write_bytes(b"book")
    solutions.write_bytes(b"solutions")
    (production / "publication-report.json").write_text(
        json.dumps({"pdf_path": "/books/session-example/build/async-rl.pdf"}),
        encoding="utf-8",
    )

    assert find_pdf(tmp_path) == book


def test_find_pdf_fallback_excludes_solutions(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir()
    book = build / "book.pdf"
    solutions = build / "book-solutions.pdf"
    book.write_bytes(b"book")
    solutions.write_bytes(b"solutions")

    assert find_pdf(tmp_path) == book


def test_list_artifacts_hides_runtime_files_and_returns_version(tmp_path: Path) -> None:
    visible = tmp_path / "production" / "research.json"
    hidden_state = tmp_path / "state" / "usage.json"
    hidden_preview = tmp_path / "build" / "review-preview" / "page-1.png"
    for path in (visible, hidden_state, hidden_preview):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    artifacts = list_artifacts(tmp_path)

    assert [artifact["path"] for artifact in artifacts] == ["production/research.json"]
    assert artifacts[0]["modified_ns"] == visible.stat().st_mtime_ns
    assert artifacts[0]["is_primary"] is False
