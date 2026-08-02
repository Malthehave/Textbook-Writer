from __future__ import annotations

from pathlib import Path

import pytest

import textbook_writer.runtime.agents as agents_runtime
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
