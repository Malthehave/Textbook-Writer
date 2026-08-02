"""OpenAI Agents SDK stream events → AI SDK UI message stream (SSE)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from openai.types.responses import (
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseTextDeltaEvent,
)


def _sse(payload: dict[str, Any] | str) -> str:
    if isinstance(payload, str):
        return f"data: {payload}\n\n"
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _call_id(raw: Any) -> str:
    if isinstance(raw, dict):
        return str(raw.get("call_id") or raw.get("id") or f"call_{uuid4().hex[:12]}")
    return str(
        getattr(raw, "call_id", None)
        or getattr(raw, "id", None)
        or f"call_{uuid4().hex[:12]}"
    )


def _tool_name(raw: Any) -> str:
    if isinstance(raw, dict):
        return str(raw.get("name") or "tool")
    return str(getattr(raw, "name", None) or "tool")


def _tool_arguments(raw: Any) -> Any:
    args = raw.get("arguments") if isinstance(raw, dict) else getattr(raw, "arguments", None)
    if args is None:
        return {}
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {"raw": args}
    return args


def _tool_output(item: Any) -> Any:
    output = getattr(item, "output", None)
    if output is not None:
        return output
    raw = getattr(item, "raw_item", None)
    if isinstance(raw, dict):
        return raw.get("output") or raw.get("result") or ""
    return getattr(raw, "output", None) or getattr(raw, "result", None) or ""


def _book_cost_chunk(payload: dict[str, Any]) -> str:
    return _sse(
        {
            "type": "data-book-cost",
            "data": payload,
            "transient": True,
        }
    )


def _drain_cost_updates(
    cost_updates: asyncio.Queue[dict[str, Any]] | None,
) -> list[str]:
    if cost_updates is None:
        return []
    chunks: list[str] = []
    while True:
        try:
            update = cost_updates.get_nowait()
        except asyncio.QueueEmpty:
            break
        chunks.append(_book_cost_chunk(update))
    return chunks


async def stream_agent_run(
    result: Any,
    *,
    cost_updates: asyncio.Queue[dict[str, Any]] | None = None,
    initial_cost: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Yield AI SDK UI-message-stream SSE chunks from Runner.run_streamed()."""

    message_id = f"msg_{uuid4().hex}"
    text_id = f"text_{uuid4().hex}"
    reasoning_id = f"reasoning_{uuid4().hex}"
    text_open = False
    reasoning_open = False

    def close_text() -> list[str]:
        nonlocal text_open, text_id
        if not text_open:
            return []
        chunks = [_sse({"type": "text-end", "id": text_id})]
        text_open = False
        text_id = f"text_{uuid4().hex}"
        return chunks

    def close_reasoning() -> list[str]:
        nonlocal reasoning_open, reasoning_id
        if not reasoning_open:
            return []
        chunks = [_sse({"type": "reasoning-end", "id": reasoning_id})]
        reasoning_open = False
        reasoning_id = f"reasoning_{uuid4().hex}"
        return chunks

    yield _sse({"type": "start", "messageId": message_id})
    yield _sse({"type": "start-step"})
    if initial_cost is not None:
        yield _book_cost_chunk(initial_cost)

    try:
        async for event in result.stream_events():
            for chunk in _drain_cost_updates(cost_updates):
                yield chunk
            etype = getattr(event, "type", None)

            if etype == "raw_response_event":
                data = event.data
                if isinstance(data, ResponseTextDeltaEvent):
                    for chunk in close_reasoning():
                        yield chunk
                    if not text_open:
                        yield _sse({"type": "text-start", "id": text_id})
                        text_open = True
                    yield _sse(
                        {"type": "text-delta", "id": text_id, "delta": data.delta}
                    )
                elif isinstance(
                    data,
                    (ResponseReasoningSummaryTextDeltaEvent, ResponseReasoningTextDeltaEvent),
                ):
                    for chunk in close_text():
                        yield chunk
                    if not reasoning_open:
                        yield _sse({"type": "reasoning-start", "id": reasoning_id})
                        reasoning_open = True
                    yield _sse(
                        {
                            "type": "reasoning-delta",
                            "id": reasoning_id,
                            "delta": data.delta,
                        }
                    )
                continue

            if etype == "run_item_stream_event":
                name = getattr(event, "name", None)
                item = getattr(event, "item", None)
                if name == "tool_called" and item is not None:
                    for chunk in close_text():
                        yield chunk
                    for chunk in close_reasoning():
                        yield chunk
                    raw = getattr(item, "raw_item", item)
                    call_id = _call_id(raw)
                    tool_name = _tool_name(raw)
                    yield _sse(
                        {
                            "type": "tool-input-start",
                            "toolCallId": call_id,
                            "toolName": tool_name,
                            "dynamic": True,
                        }
                    )
                    yield _sse(
                        {
                            "type": "tool-input-available",
                            "toolCallId": call_id,
                            "toolName": tool_name,
                            "input": _tool_arguments(raw),
                            "dynamic": True,
                        }
                    )
                elif name == "tool_output" and item is not None:
                    raw = getattr(item, "raw_item", item)
                    yield _sse(
                        {
                            "type": "tool-output-available",
                            "toolCallId": _call_id(raw),
                            "output": _tool_output(item),
                        }
                    )
                    yield _sse({"type": "finish-step"})
                    yield _sse({"type": "start-step"})
                continue

    except Exception as exc:  # noqa: BLE001 — surface to UI stream
        detail = str(exc).strip() or exc.__class__.__name__
        yield _sse({"type": "error", "errorText": f"Run failed: {detail}"})
    finally:
        if not bool(getattr(result, "is_complete", False)):
            cancel = getattr(result, "cancel", None)
            if callable(cancel):
                try:
                    cancel(mode="immediate")
                except Exception:  # noqa: BLE001 — best-effort teardown
                    pass

    for chunk in close_text():
        yield chunk
    for chunk in close_reasoning():
        yield chunk
    for chunk in _drain_cost_updates(cost_updates):
        yield chunk
    yield _sse({"type": "finish-step"})
    yield _sse({"type": "finish"})
    yield _sse("[DONE]")
