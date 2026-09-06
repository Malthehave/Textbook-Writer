"""SQLite chat sessions + book filesystem helpers."""

from __future__ import annotations

import json
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subagent_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            outer_tool_call_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_subagent_events_session_call
        ON subagent_events (session_id, outer_tool_call_id, id)
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

    def append_subagent_events(
        self, session_id: str, events: list[dict[str, Any]]
    ) -> None:
        if not events:
            return
        now = datetime.now(UTC).isoformat()
        with _connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO subagent_events (
                    session_id,
                    outer_tool_call_id,
                    agent_name,
                    event_type,
                    payload_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        str(event["outer_tool_call_id"]),
                        str(event["agent_name"]),
                        str(event["event_type"]),
                        json.dumps(event.get("payload", {}), default=str),
                        now,
                    )
                    for event in events
                ],
            )
            conn.commit()

    def list_subagent_events(self, session_id: str) -> list[dict[str, Any]]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    outer_tool_call_id,
                    agent_name,
                    event_type,
                    payload_json,
                    created_at
                FROM subagent_events
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        return [
            {
                "outer_tool_call_id": row["outer_tool_call_id"],
                "agent_name": row["agent_name"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def list_artifacts(root: Path) -> list[dict[str, str | int | bool]]:
    root = root.resolve()
    if not root.is_dir():
        return []
    primary_pdf = find_pdf(root)
    items: list[dict[str, str | int | bool]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts[0] in {".agents", ".cache", "state"}:
            continue
        if relative.parts[:2] == ("build", "review-preview"):
            continue
        if path.suffix.lower() not in {".json", ".pdf", ".png", ".html", ".typ", ".md"}:
            continue
        if path.name.endswith(".sqlite") or path.name.endswith(".tmp"):
            continue
        stat = path.stat()
        items.append(
            {
                "path": relative.as_posix(),
                "bytes": stat.st_size,
                "kind": path.suffix.lower().lstrip("."),
                "modified_ns": stat.st_mtime_ns,
                "is_primary": path.resolve() == primary_pdf,
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
    root = root.resolve()
    build = root / "build"
    if not build.is_dir():
        return None

    # The publication report is the source of truth. Its path can contain the
    # container's /books prefix, so remap the filename into this process's root.
    report = root / "production" / "publication-report.json"
    if report.is_file():
        try:
            reported_path = json.loads(report.read_text(encoding="utf-8")).get("pdf_path")
        except (json.JSONDecodeError, OSError):
            reported_path = None
        if isinstance(reported_path, str) and reported_path:
            candidate = (build / Path(reported_path).name).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                return candidate

    pdfs = [path for path in build.glob("*.pdf") if path.is_file()]
    primary_pdfs = [path for path in pdfs if not path.stem.endswith("-solutions")]
    candidates = primary_pdfs or pdfs
    return max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None


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
