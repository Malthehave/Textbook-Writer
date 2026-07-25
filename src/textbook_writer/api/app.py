"""FastAPI app: stream textbook manager via AI SDK UI message protocol."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from agents import Runner, SQLiteSession
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from textbook_writer.api.debug_log import read_debug_bundle
from textbook_writer.api.history import session_items_to_ui_messages
from textbook_writer.api.store import (
    SessionRow,
    SessionStore,
    find_pdf,
    list_artifacts,
    read_artifact_text,
)
from textbook_writer.api.stream import stream_agent_run
from textbook_writer.runtime.agents.manager import build_manager_agent
from textbook_writer.runtime.workspace import initialize_workspace
from textbook_writer.runtime import workspace as workspace_mod

load_dotenv()

API_ROOT = Path(os.environ.get("TEXTBOOK_API_ROOT", Path.cwd())).resolve()
SESSIONS_DB = Path(
    os.environ.get("TEXTBOOK_SESSIONS_DB", API_ROOT / "output" / "ui-sessions.sqlite")
).resolve()
BOOKS_ROOT_RESOLVED = Path(
    os.environ.get("TEXTBOOK_BOOKS_ROOT", API_ROOT / "output" / "books")
).resolve()
workspace_mod.BOOKS_ROOT = BOOKS_ROOT_RESOLVED

store = SessionStore(SESSIONS_DB)
app = FastAPI(title="Textbook Writer API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-vercel-ai-ui-message-stream", "x-textbook-session-id"],
)


class CreateSessionResponse(BaseModel):
    id: str
    book_id: str
    workspace: str
    title: str


class ChatRequest(BaseModel):
    id: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    trigger: str | None = None


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        parts = message.get("parts")
        if isinstance(parts, list):
            chunks = [
                str(part.get("text", ""))
                for part in parts
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            text = "".join(chunks).strip()
            if text:
                return text
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    raise HTTPException(status_code=400, detail="no user message in request")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sessions")
def get_sessions() -> list[dict[str, str]]:
    return [
        {
            "id": row.id,
            "book_id": row.book_id,
            "workspace": row.workspace,
            "title": row.title,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in store.list()
    ]


@app.post("/api/sessions", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    BOOKS_ROOT_RESOLVED.mkdir(parents=True, exist_ok=True)
    workspace = initialize_workspace()
    session_id = f"session-{uuid4().hex[:10]}"
    row = store.create(
        session_id=session_id,
        book_id=workspace.book_id,
        workspace=workspace.root,
        title="Untitled book",
    )
    return CreateSessionResponse(
        id=row.id,
        book_id=row.book_id,
        workspace=row.workspace,
        title=row.title,
    )


def _agent_session(row: SessionRow) -> SQLiteSession:
    workspace = Path(row.workspace)
    session_db = workspace / "state" / "product-sessions.sqlite"
    session_db.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteSession(f"{row.book_id}-manager", db_path=session_db)


@app.get("/api/sessions/{session_id}/messages")
async def session_messages(session_id: str) -> list[dict[str, Any]]:
    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    session = _agent_session(row)
    items = await session.get_items()
    return session_items_to_ui_messages([dict(item) for item in items])


@app.get("/api/sessions/{session_id}/debug")
def session_debug(session_id: str) -> dict[str, Any]:
    """Inspect stream/error logs for a book session (for agent debugging)."""

    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    bundle = read_debug_bundle(Path(row.workspace))
    bundle["session"] = {
        "id": row.id,
        "book_id": row.book_id,
        "title": row.title,
        "updated_at": row.updated_at,
    }
    return bundle


@app.get("/api/sessions/{session_id}/artifacts")
def session_artifacts(session_id: str) -> list[dict[str, str | int]]:
    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return list_artifacts(Path(row.workspace))


@app.get("/api/sessions/{session_id}/artifacts/content")
def session_artifact_content(
    session_id: str,
    path: str = Query(..., min_length=1),
) -> dict[str, str]:
    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        content = read_artifact_text(Path(row.workspace), path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": path, "content": content}


@app.get("/api/sessions/{session_id}/pdf")
def session_pdf(session_id: str) -> FileResponse:
    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    pdf = find_pdf(Path(row.workspace))
    if pdf is None:
        raise HTTPException(status_code=404, detail="no PDF yet")
    return FileResponse(pdf, media_type="application/pdf", filename=pdf.name)


@app.get("/api/sessions/{session_id}/files/{file_path:path}")
def session_file(session_id: str, file_path: str) -> FileResponse:
    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    workspace = Path(row.workspace).resolve()
    path = (workspace / file_path).resolve()
    if not path.is_relative_to(workspace) or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


@app.post("/api/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    session_id = body.id
    if not session_id:
        raise HTTPException(status_code=400, detail="chat id (session id) is required")
    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found; create one first")

    user_text = _last_user_text(body.messages)
    workspace = Path(row.workspace)
    agent = build_manager_agent(workspace=workspace, book_id=row.book_id)
    session = _agent_session(row)

    if row.title == "Untitled book" and user_text:
        title = user_text.strip().splitlines()[0][:80]
        store.touch(session_id, title=title)
    else:
        store.touch(session_id)

    result = Runner.run_streamed(
        agent,
        user_text,
        session=session,
        max_turns=40,
    )

    return StreamingResponse(
        stream_agent_run(result, workspace=workspace),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
            "x-textbook-session-id": session_id,
        },
    )
