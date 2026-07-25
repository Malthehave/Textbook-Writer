"""Per-session stream/debug logs agents can inspect without the UI."""

from __future__ import annotations

import json
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def state_dir(workspace: Path) -> Path:
    path = workspace.resolve() / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def stream_log_path(workspace: Path) -> Path:
    return state_dir(workspace) / "ui-stream.jsonl"


def error_log_path(workspace: Path) -> Path:
    return state_dir(workspace) / "ui-errors.log"


def append_stream_event(workspace: Path, payload: dict[str, Any]) -> None:
    """Append one compact SSE payload (no huge tool blobs)."""

    record = {
        "ts": datetime.now(UTC).isoformat(),
        "type": payload.get("type"),
    }
    for key in (
        "toolCallId",
        "toolName",
        "id",
        "errorText",
        "messageId",
    ):
        if key in payload:
            value = payload[key]
            if isinstance(value, str) and len(value) > 500:
                value = value[:500] + "…"
            record[key] = value
    data = payload.get("data")
    if isinstance(data, dict):
        compact = {
            k: data[k]
            for k in ("label", "agentName", "kind", "status", "parentToolCallId", "toolCallId", "toolName")
            if k in data
        }
        if "errorText" in data:
            err = str(data["errorText"])
            compact["errorText"] = err if len(err) <= 500 else err[:500] + "…"
        if compact:
            record["data"] = compact
    path = stream_log_path(workspace)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


def append_error(workspace: Path, message: str, exc: BaseException | None = None) -> None:
    path = error_log_path(workspace)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n--- {datetime.now(UTC).isoformat()} ---\n")
        handle.write(message.rstrip() + "\n")
        if exc is not None:
            handle.write("".join(traceback.format_exception(exc)))


def read_debug_bundle(workspace: Path, *, stream_tail: int = 200) -> dict[str, Any]:
    workspace = workspace.resolve()
    stream_path = stream_log_path(workspace)
    error_path = error_log_path(workspace)
    stream_lines: list[str] = []
    if stream_path.is_file():
        stream_lines = stream_path.read_text(encoding="utf-8", errors="replace").splitlines()
        stream_lines = stream_lines[-stream_tail:]
    errors = ""
    if error_path.is_file():
        errors = error_path.read_text(encoding="utf-8", errors="replace")[-20_000:]
    return {
        "workspace": str(workspace),
        "stream_log": str(stream_path),
        "error_log": str(error_path),
        "stream_events": [json.loads(line) for line in stream_lines if line.strip()],
        "errors_tail": errors,
    }
