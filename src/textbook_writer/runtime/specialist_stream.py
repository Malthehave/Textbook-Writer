"""Bridge nested Agent.as_tool() streams into the UI SSE multiplexer.

When a specialist runs as a tool, Agents SDK can call ``on_stream``. Those
events are pushed onto a context-local queue that ``stream_agent_run`` drains
concurrently with the parent manager stream.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from agents import AgentToolStreamEvent
from agents.items import MessageOutputItem, ReasoningItem, ToolCallItem, ToolCallOutputItem
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent

SPECIALIST_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "research-scout",
        "research-architect",
        "research-auditor",
        "curriculum-architect",
        "coverage-auditor",
        "curriculum-repair",
        "chapter-writer",
        "html-diagram-author",
        "independent-verifier",
        "solution-comparator",
        "exercise-repair",
        "continuity-editor",
    }
)

_specialist_queue: ContextVar[asyncio.Queue[dict[str, Any] | None] | None] = ContextVar(
    "specialist_stream_queue",
    default=None,
)


def bind_specialist_queue(queue: asyncio.Queue[dict[str, Any] | None]) -> Any:
    return _specialist_queue.set(queue)


def reset_specialist_queue(token: Any) -> None:
    _specialist_queue.reset(token)


def is_specialist_tool(tool_name: str) -> bool:
    return tool_name in SPECIALIST_TOOL_NAMES


def _tool_name(raw: Any) -> str:
    return str(getattr(raw, "name", None) or getattr(raw, "tool_name", None) or "tool")


def _tool_call_id(raw: Any) -> str:
    """Prefer Responses ``call_id``; never confuse it with item ``id`` (``fc_…``)."""

    if isinstance(raw, dict):
        cid = raw.get("call_id")
        if cid:
            return str(cid)
        return f"call_{uuid4().hex[:12]}"
    cid = getattr(raw, "call_id", None)
    if cid:
        return str(cid)
    return f"call_{uuid4().hex[:12]}"


def _reasoning_text(item: ReasoningItem) -> str:
    raw = item.raw_item
    parts: list[str] = []
    summary = getattr(raw, "summary", None) or []
    for block in summary:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    content = getattr(raw, "content", None)
    if isinstance(content, str) and content.strip():
        parts.append(content)
    elif isinstance(content, list):
        for block in content:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
    return "\n".join(parts).strip()


def _parent_ids(payload: AgentToolStreamEvent) -> tuple[str, str]:
    tool_call = payload.get("tool_call")
    parent_id = _tool_call_id(tool_call) if tool_call is not None else f"call_{uuid4().hex[:12]}"
    agent_name = (
        _tool_name(tool_call)
        if tool_call is not None
        else getattr(payload["agent"], "name", "specialist")
    )
    return parent_id, str(agent_name)


def _chunk(parent_tool_call_id: str, agent_name: str, **fields: Any) -> dict[str, Any]:
    return {
        "type": "data-specialist",
        "data": {
            "parentToolCallId": parent_tool_call_id,
            "agentName": agent_name,
            **fields,
        },
        "transient": True,
    }


def nested_event_chunks(payload: AgentToolStreamEvent) -> list[dict[str, Any]]:
    """Convert one nested stream event into zero or more UI data chunks."""

    parent_id, agent_name = _parent_ids(payload)
    event = payload["event"]
    chunks: list[dict[str, Any]] = []

    if isinstance(event, AgentUpdatedStreamEvent):
        name = getattr(event.new_agent, "name", agent_name)
        chunks.append(
            _chunk(parent_id, agent_name, kind="status", status="running", label=str(name))
        )
        return chunks

    if isinstance(event, RawResponsesStreamEvent):
        data = event.data
        etype = getattr(data, "type", None)
        delta = getattr(data, "delta", None)
        if not delta:
            return chunks
        if etype == "response.output_text.delta":
            chunks.append(_chunk(parent_id, agent_name, kind="text-delta", text=str(delta)))
        elif etype in {"response.reasoning_summary_text.delta", "response.reasoning_text.delta"}:
            chunks.append(
                _chunk(parent_id, agent_name, kind="reasoning-delta", text=str(delta))
            )
        return chunks

    if not isinstance(event, RunItemStreamEvent):
        return chunks

    item = event.item
    if isinstance(item, ToolCallItem):
        # Status-only for nested tools — do not multiplex full nested I/O into the UI.
        raw = item.raw_item
        chunks.append(
            _chunk(
                parent_id,
                agent_name,
                kind="status",
                status="running",
                label=f"Using {_tool_name(raw)}",
            )
        )
    elif isinstance(item, ToolCallOutputItem):
        pass
    elif isinstance(item, ReasoningItem):
        text = _reasoning_text(item)
        if text:
            chunks.append(_chunk(parent_id, agent_name, kind="reasoning-delta", text=text))
    elif isinstance(item, MessageOutputItem):
        # Prefer streamed text deltas; skip the final full message to avoid duplicates.
        pass

    return chunks


async def emit_specialist_stream_event(payload: AgentToolStreamEvent) -> None:
    """on_stream callback for Agent.as_tool() specialists."""

    queue = _specialist_queue.get()
    if queue is None:
        return
    for chunk in nested_event_chunks(payload):
        await queue.put(chunk)
