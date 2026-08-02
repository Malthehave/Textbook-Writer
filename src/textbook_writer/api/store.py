"""SQLite chat sessions + book filesystem helpers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SessionRow:
    id: str
    title: str
    created_at: str
    updated_at: str


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'Untitled book',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.resolve()

    def create(self, *, session_id: str, title: str = "Untitled book") -> SessionRow:
        now = datetime.now(UTC).isoformat()
        row = SessionRow(id=session_id, title=title, created_at=now, updated_at=now)
        with _connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (row.id, row.title, row.created_at, row.updated_at),
            )
            conn.commit()
        return row

    def list(self) -> list[SessionRow]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions "
                "ORDER BY updated_at DESC"
            ).fetchall()
        return [SessionRow(**dict(row)) for row in rows]

    def get(self, session_id: str) -> SessionRow | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return SessionRow(**dict(row)) if row else None

    def touch(self, session_id: str, *, title: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        with _connect(self.db_path) as conn:
            if title is None:
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET updated_at = ?, title = ? WHERE id = ?",
                    (now, title, session_id),
                )
            conn.commit()


def list_artifacts(root: Path) -> list[dict[str, str | int]]:
    root = root.resolve()
    if not root.is_dir():
        return []
    items: list[dict[str, str | int]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".pdf", ".png", ".html", ".typ", ".md"}:
            continue
        if path.name.endswith(".sqlite") or path.name.endswith(".tmp"):
            continue
        items.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "kind": path.suffix.lower().lstrip("."),
            }
        )
    return items


def read_artifact_text(root: Path, relative: str, *, limit: int = 200_000) -> str:
    path = (root.resolve() / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise FileNotFoundError(relative)
    if path.suffix.lower() in {".png", ".pdf"}:
        raise ValueError("binary artifact; use the file endpoint")
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + "\n…[truncated]"
    return text


def find_pdf(root: Path) -> Path | None:
    build = root.resolve() / "build"
    if not build.is_dir():
        return None
    pdfs = sorted(build.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def read_debug_bundle(root: Path) -> dict[str, Any]:
    root = root.resolve()
    error_path = root / "state" / "ui-errors.log"
    errors = ""
    if error_path.is_file():
        errors = error_path.read_text(encoding="utf-8", errors="replace")[-20_000:]
    return {
        "root": str(root),
        "error_log": str(error_path),
        "errors_tail": errors,
    }
