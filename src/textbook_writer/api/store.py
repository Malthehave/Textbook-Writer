"""SQLite registry of book sessions (separate from Agents SDK session history)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SessionRow:
    id: str
    book_id: str
    workspace: str
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
            book_id TEXT NOT NULL,
            workspace TEXT NOT NULL,
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

    def create(self, *, session_id: str, book_id: str, workspace: Path, title: str = "Untitled book") -> SessionRow:
        now = datetime.now(UTC).isoformat()
        row = SessionRow(
            id=session_id,
            book_id=book_id,
            workspace=str(workspace.resolve()),
            title=title,
            created_at=now,
            updated_at=now,
        )
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, book_id, workspace, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (row.id, row.book_id, row.workspace, row.title, row.created_at, row.updated_at),
            )
            conn.commit()
        return row

    def list(self) -> list[SessionRow]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [SessionRow(**dict(row)) for row in rows]

    def get(self, session_id: str) -> SessionRow | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
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


def list_artifacts(workspace: Path) -> list[dict[str, str | int]]:
    """List generated JSON/PDF/PNG/HTML artifacts under a book workspace."""

    workspace = workspace.resolve()
    if not workspace.is_dir():
        return []
    items: list[dict[str, str | int]] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".pdf", ".png", ".html", ".typ", ".md"}:
            continue
        if path.name.endswith(".sqlite") or path.name.endswith(".tmp"):
            continue
        rel = path.relative_to(workspace).as_posix()
        items.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "kind": path.suffix.lower().lstrip("."),
            }
        )
    return items


def read_artifact_text(workspace: Path, relative: str, *, limit: int = 200_000) -> str:
    path = (workspace.resolve() / relative).resolve()
    if not path.is_relative_to(workspace.resolve()) or not path.is_file():
        raise FileNotFoundError(relative)
    if path.suffix.lower() in {".png", ".pdf"}:
        raise ValueError("binary artifact; use the file endpoint")
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + "\n…[truncated]"
    return text


def find_pdf(workspace: Path) -> Path | None:
    build = workspace.resolve() / "build"
    if not build.is_dir():
        return None
    pdfs = sorted(build.glob("*.pdf"))
    return pdfs[0] if pdfs else None
