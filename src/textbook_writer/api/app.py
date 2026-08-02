"""FastAPI routes for the textbook manager UI."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from agents import Runner, SQLiteSession
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from textbook_writer.api.history import session_items_to_ui_messages
from textbook_writer.api.progress import derive_book_progress
from textbook_writer.api.store import (
    SessionRow,
    SessionStore,
    find_pdf,
    list_artifacts,
    read_artifact_text,
    read_debug_bundle,
)
from textbook_writer.api.stream import stream_agent_run
from textbook_writer.api.subagent_events import normalize_subagent_event
from textbook_writer.runtime.agents import (
    create_session_book,
    sandbox_tool_run_config,
    session_book_root,
)
from textbook_writer.runtime.agents.manager import build_manager_agent
from textbook_writer.runtime.agents.persona_interviewer import (
    build_persona_interviewer_agent,
)
from textbook_writer.runtime.persona import (
    INTERVIEW_SESSION_ID,
    interview_session_db,
    load_persona,
    persona_dir,
    persona_path,
    save_persona,
)
from textbook_writer.runtime.usage_ledger import BookCostHooks, load_usage_summary

load_dotenv()

API_ROOT = Path(os.environ.get("TEXTBOOK_API_ROOT", Path.cwd())).resolve()
SESSIONS_DB = Path(
    os.environ.get("TEXTBOOK_SESSIONS_DB", API_ROOT / "output" / "ui-sessions.sqlite")
).resolve()

store = SessionStore(SESSIONS_DB)
active_session_runs: set[str] = set()
persona_interview_active = False
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
    title: str


class ChatRequest(BaseModel):
    id: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    trigger: str | None = None


class PersonaUpdateRequest(BaseModel):
    markdown: str = ""


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


def _book_root(session_id: str) -> Path:
    try:
        root = session_book_root(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not root.is_dir():
        raise HTTPException(status_code=404, detail="book workspace not found")
    return root


def _agent_session(row: SessionRow, book_root: Path) -> SQLiteSession:
    session_db = book_root / "state" / "product-sessions.sqlite"
    session_db.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteSession(f"{row.id}-manager", db_path=session_db)


async def _stream_session_run(
    result: Any,
    session_id: str,
    *,
    cost_updates: asyncio.Queue[dict[str, Any]] | None = None,
    initial_cost: dict[str, Any] | None = None,
    subagent_updates: asyncio.Queue[dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    try:
        async for chunk in stream_agent_run(
            result,
            cost_updates=cost_updates,
            initial_cost=initial_cost,
            subagent_updates=subagent_updates,
            persist_subagent_events=lambda events: store.append_subagent_events(
                session_id, events
            ),
        ):
            yield chunk
    finally:
        active_session_runs.discard(session_id)


def _claim_session_run(session_id: str) -> None:
    if session_id in active_session_runs:
        raise HTTPException(
            status_code=409,
            detail="this book already has an active generation run",
        )
    active_session_runs.add(session_id)


def _claim_persona_interview() -> None:
    global persona_interview_active
    if persona_interview_active:
        raise HTTPException(
            status_code=409,
            detail="a persona interview is already running",
        )
    persona_interview_active = True


async def _stream_persona_interview(result: Any) -> AsyncIterator[str]:
    global persona_interview_active
    try:
        async for chunk in stream_agent_run(result):
            yield chunk
    finally:
        persona_interview_active = False


def _interview_session() -> SQLiteSession:
    db_path = interview_session_db()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteSession(INTERVIEW_SESSION_ID, db_path=db_path)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/persona")
def get_persona() -> dict[str, Any]:
    markdown = load_persona()
    path = persona_path()
    return {
        "markdown": markdown,
        "path": str(path.relative_to(API_ROOT)) if path.is_relative_to(API_ROOT) else str(path),
        "updated_at": (
            path.stat().st_mtime_ns if path.is_file() else None
        ),
    }


@app.put("/api/persona")
def put_persona(body: PersonaUpdateRequest) -> dict[str, Any]:
    markdown = save_persona(body.markdown)
    path = persona_path()
    return {
        "markdown": markdown,
        "path": str(path.relative_to(API_ROOT)) if path.is_relative_to(API_ROOT) else str(path),
        "updated_at": path.stat().st_mtime_ns if path.is_file() else None,
    }


@app.get("/api/persona/messages")
async def persona_messages() -> list[dict[str, Any]]:
    session = _interview_session()
    items = await session.get_items()
    return session_items_to_ui_messages([dict(item) for item in items])


@app.post("/api/persona/chat")
async def persona_chat(body: ChatRequest) -> StreamingResponse:
    global persona_interview_active
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")
    _claim_persona_interview()
    try:
        user_text = _last_user_text(body.messages)
        root = persona_dir()
        agent = build_persona_interviewer_agent()
        session = _interview_session()
        result = Runner.run_streamed(
            agent,
            user_text,
            session=session,
            max_turns=40,
            run_config=sandbox_tool_run_config(root=root),
        )
    except Exception:
        persona_interview_active = False
        raise

    return StreamingResponse(
        _stream_persona_interview(result),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


@app.get("/api/sessions")
def get_sessions() -> list[dict[str, str]]:
    return [
        {
            "id": row.id,
            "title": row.title,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in store.list()
    ]


@app.post("/api/sessions", response_model=CreateSessionResponse)
def create_session() -> CreateSessionResponse:
    session_id = f"session-{uuid4().hex[:10]}"
    try:
        create_session_book(session_id)
    except FileExistsError as exc:
        raise HTTPException(status_code=500, detail="book workspace collision") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    row = store.create(session_id=session_id, title="Untitled book")
    return CreateSessionResponse(id=row.id, title=row.title)


@app.get("/api/sessions/{session_id}/messages")
async def session_messages(session_id: str) -> list[dict[str, Any]]:
    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    book_root = _book_root(session_id)
    session = _agent_session(row, book_root)
    items = await session.get_items()
    return session_items_to_ui_messages(
        [dict(item) for item in items],
        subagent_events=store.list_subagent_events(session_id),
    )


@app.get("/api/sessions/{session_id}/debug")
def session_debug(session_id: str) -> dict[str, Any]:
    row = store.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    book_root = _book_root(session_id)
    bundle = read_debug_bundle(book_root)
    bundle["session"] = {
        "id": row.id,
        "title": row.title,
        "updated_at": row.updated_at,
    }
    return bundle


@app.get("/api/sessions/{session_id}/artifacts")
def session_artifacts(session_id: str) -> list[dict[str, str | int]]:
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    return list_artifacts(_book_root(session_id))


@app.get("/api/sessions/{session_id}/usage")
def session_usage(session_id: str) -> dict[str, Any]:
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    summary = load_usage_summary(_book_root(session_id))
    return {
        "currency": summary["currency"],
        "pricing_source": summary["pricing_source"],
        "totals": summary["totals"],
        "by_model": summary["by_model"],
        "last_call": summary["calls"][-1] if summary["calls"] else None,
    }


@app.get("/api/sessions/{session_id}/progress")
def session_progress(session_id: str) -> dict[str, Any]:
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    return derive_book_progress(_book_root(session_id))


@app.get("/api/sessions/{session_id}/subagent-events")
def session_subagent_events(session_id: str) -> list[dict[str, Any]]:
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    return store.list_subagent_events(session_id)


@app.get("/api/sessions/{session_id}/artifacts/content")
def session_artifact_content(
    session_id: str,
    path: str = Query(..., min_length=1),
) -> dict[str, str]:
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        content = read_artifact_text(_book_root(session_id), path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": path, "content": content}


@app.get("/api/sessions/{session_id}/pdf")
def session_pdf(session_id: str) -> FileResponse:
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    pdf = find_pdf(_book_root(session_id))
    if pdf is None:
        raise HTTPException(status_code=404, detail="no PDF yet")
    return FileResponse(
        pdf,
        media_type="application/pdf",
        filename=pdf.name,
        content_disposition_type="inline",
    )


@app.get("/api/sessions/{session_id}/files/{file_path:path}")
def session_file(session_id: str, file_path: str) -> FileResponse:
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    root = _book_root(session_id)
    path = (root / file_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
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
    _claim_session_run(session_id)

    cost_updates: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    subagent_updates: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def on_subagent_stream(event: Any) -> None:
        normalized = normalize_subagent_event(event)
        if normalized is not None:
            await subagent_updates.put(normalized)

    try:
        book_root = _book_root(session_id)
        user_text = _last_user_text(body.messages)
        cost_hooks = BookCostHooks(book_root=book_root, updates=cost_updates)
        agent = build_manager_agent(
            book_root=book_root,
            hooks=cost_hooks,
            on_subagent_stream=on_subagent_stream,
            learner_persona=load_persona(),
        )
        session = _agent_session(row, book_root)

        if row.title == "Untitled book" and user_text:
            title = user_text.strip().splitlines()[0][:80]
            store.touch(session_id, title=title)
        else:
            store.touch(session_id)

        result = Runner.run_streamed(
            agent,
            user_text,
            session=session,
            max_turns=200,
            hooks=cost_hooks,
            run_config=sandbox_tool_run_config(root=book_root),
        )
    except Exception:
        active_session_runs.discard(session_id)
        raise

    return StreamingResponse(
        _stream_session_run(
            result,
            session_id,
            cost_updates=cost_updates,
            initial_cost=cost_hooks.snapshot(),
            subagent_updates=subagent_updates,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
            "x-textbook-session-id": session_id,
        },
    )
