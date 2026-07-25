"""Map OpenAI Agents SDK streamed events → AI SDK UI message stream (SSE).

This is a thin bridge only. It does not modify Agents SDK behavior.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

# No parent/nested progress for this long → cancel and surface an error (do not heartbeat forever).
STALL_SECONDS = 180.0

from agents import ItemHelpers
from agents.items import (
    MessageOutputItem,
    ReasoningItem,
    ToolCallItem,
    ToolCallOutputItem,
)
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent

from textbook_writer.api.debug_log import append_error, append_stream_event
from textbook_writer.runtime.specialist_stream import (
    bind_specialist_queue,
    is_specialist_tool,
    reset_specialist_queue,
)


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _call_id(item: ToolCallItem | ToolCallOutputItem) -> str:
    """Responses API correlation id for tool call ↔ output (not item id ``fc_…``)."""

    raw = item.raw_item
    cid = raw.get("call_id") if isinstance(raw, dict) else getattr(raw, "call_id", None)
    return str(cid) if cid else f"call_{uuid4().hex[:12]}"


def _tool_name(item: ToolCallItem | ToolCallOutputItem) -> str:
    raw = item.raw_item
    name = (
        (raw.get("name") if isinstance(raw, dict) else None)
        or getattr(raw, "name", None)
        or getattr(item, "tool_name", None)
    )
    return str(name or "tool")


def _tool_arguments(item: ToolCallItem) -> Any:
    raw = item.raw_item
    args = raw.get("arguments") if isinstance(raw, dict) else getattr(raw, "arguments", None)
    if args is None:
        return {}
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {"raw": args}
    return args


def _tool_output(item: ToolCallOutputItem) -> Any:
    if item.output is not None:
        return item.output
    raw = item.raw_item
    if isinstance(raw, dict):
        return raw.get("output") or raw.get("result") or ""
    return getattr(raw, "output", None) or getattr(raw, "result", None) or ""


def _tool_error(output: Any) -> str | None:
    if output is None:
        return None
    text = output if isinstance(output, str) else str(output)
    lower = text.lower()
    if "an error occurred while running the tool" in lower:
        return text.strip()
    if "invalid_request_error" in lower or "error code: 400" in lower:
        return text.strip()
    return None


def _reasoning_text(item: ReasoningItem) -> str:
    raw = item.raw_item
    parts: list[str] = []
    for block in getattr(raw, "summary", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    content = getattr(raw, "content", None)
    if isinstance(content, str) and content.strip():
        parts.append(content)
    elif isinstance(content, list):
        for block in content:
            text = getattr(block, "text", None) or (
                block.get("text") if isinstance(block, dict) else None
            )
            if text:
                parts.append(str(text))
    return "\n".join(parts).strip()


def _status(label: str) -> dict[str, Any]:
    return {"type": "data-run-status", "data": {"label": label}, "transient": True}


def _tool_start(call_id: str, name: str, arguments: Any) -> list[dict[str, Any]]:
    return [
        {
            "type": "tool-input-start",
            "toolCallId": call_id,
            "toolName": name,
            "dynamic": True,
        },
        {
            "type": "tool-input-available",
            "toolCallId": call_id,
            "toolName": name,
            "input": arguments,
            "dynamic": True,
        },
    ]


class _Mapper:
    """Stateful Agents SDK event → AI SDK UI chunks."""

    def __init__(self) -> None:
        self.text_id: str | None = None
        self.reasoning_id: str | None = None
        self.started_tools: set[str] = set()
        self.specialists: dict[str, str] = {}
        self.label = "Manager starting…"

    def map_event(self, event: Any) -> Iterator[dict[str, Any]]:
        if isinstance(event, AgentUpdatedStreamEvent):
            name = getattr(event.new_agent, "name", "agent")
            self.label = f"Agent · {name}"
            yield {"type": "data-agent", "data": {"name": name}}
            yield _status(self.label)
            return

        if isinstance(event, RawResponsesStreamEvent):
            yield from self._map_raw(event.data)
            return

        if isinstance(event, RunItemStreamEvent):
            yield from self._map_item(event.item)

    def _map_raw(self, data: Any) -> Iterator[dict[str, Any]]:
        etype = getattr(data, "type", None)
        delta = getattr(data, "delta", None)
        if not delta:
            return
        if etype == "response.output_text.delta":
            self.label = "Manager writing…"
            if self.text_id is None:
                self.text_id = f"text_{uuid4().hex}"
                yield {"type": "text-start", "id": self.text_id}
            yield {"type": "text-delta", "id": self.text_id, "delta": str(delta)}
        elif etype in {
            "response.reasoning_summary_text.delta",
            "response.reasoning_text.delta",
        }:
            self.label = "Manager reasoning…"
            if self.reasoning_id is None:
                self.reasoning_id = f"reasoning_{uuid4().hex}"
                yield {"type": "reasoning-start", "id": self.reasoning_id}
            yield {
                "type": "reasoning-delta",
                "id": self.reasoning_id,
                "delta": str(delta),
            }

    def _map_item(self, item: Any) -> Iterator[dict[str, Any]]:
        if isinstance(item, ToolCallItem):
            call_id = _call_id(item)
            name = _tool_name(item)
            self.label = f"Running · {name}"
            yield _status(self.label)
            if call_id not in self.started_tools:
                self.started_tools.add(call_id)
                yield from _tool_start(call_id, name, _tool_arguments(item))
            if is_specialist_tool(name):
                self.specialists[call_id] = name
                yield {
                    "type": "data-specialist",
                    "data": {
                        "parentToolCallId": call_id,
                        "agentName": name,
                        "kind": "status",
                        "status": "running",
                    },
                    "transient": True,
                }
            return

        if isinstance(item, ToolCallOutputItem):
            call_id = _call_id(item)
            name = self.specialists.get(call_id) or _tool_name(item)
            output = _tool_output(item)
            if call_id not in self.started_tools:
                self.started_tools.add(call_id)
                yield from _tool_start(call_id, name, {})
            error = _tool_error(output)
            if error:
                self.label = f"Tool failed · {name}"
                yield {
                    "type": "tool-output-error",
                    "toolCallId": call_id,
                    "errorText": error,
                }
            else:
                self.label = "Manager continuing…"
                yield {
                    "type": "tool-output-available",
                    "toolCallId": call_id,
                    "output": output,
                }
            specialist = self.specialists.pop(call_id, None)
            if specialist is not None:
                yield {
                    "type": "data-specialist",
                    "data": {
                        "parentToolCallId": call_id,
                        "agentName": specialist,
                        "kind": "status",
                        "status": "failed" if error else "completed",
                        "errorText": error,
                    },
                    "transient": True,
                }
            yield _status(self.label)
            return

        if isinstance(item, ReasoningItem):
            if self.reasoning_id is not None:
                yield {"type": "reasoning-end", "id": self.reasoning_id}
                self.reasoning_id = None
                return
            text = _reasoning_text(item)
            if not text:
                return
            self.reasoning_id = f"reasoning_{uuid4().hex}"
            yield {"type": "reasoning-start", "id": self.reasoning_id}
            yield {"type": "reasoning-delta", "id": self.reasoning_id, "delta": text}
            yield {"type": "reasoning-end", "id": self.reasoning_id}
            self.reasoning_id = None
            return

        if isinstance(item, MessageOutputItem) and self.text_id is None:
            text = ItemHelpers.text_message_output(item)
            if not text:
                return
            self.text_id = f"text_{uuid4().hex}"
            yield {"type": "text-start", "id": self.text_id}
            yield {"type": "text-delta", "id": self.text_id, "delta": text}

    def close_parts(self) -> Iterator[dict[str, Any]]:
        if self.reasoning_id is not None:
            yield {"type": "reasoning-end", "id": self.reasoning_id}
            self.reasoning_id = None
        if self.text_id is not None:
            yield {"type": "text-end", "id": self.text_id}
            self.text_id = None


async def stream_agent_run(
    result: Any,
    *,
    workspace: Path | None = None,
    stall_seconds: float = STALL_SECONDS,
) -> AsyncIterator[str]:
    """Yield AI SDK UI-message-stream SSE chunks from Runner.run_streamed()."""

    mapper = _Mapper()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    queue_token = bind_specialist_queue(queue)
    last_progress = time.monotonic()
    stalled = False

    def emit(payload: dict[str, Any]) -> str:
        if workspace is not None:
            try:
                append_stream_event(workspace, payload)
            except OSError:
                pass
        return _sse(payload)

    def mark_progress() -> None:
        nonlocal last_progress
        last_progress = time.monotonic()

    yield emit({"type": "start", "messageId": f"msg_{uuid4().hex}"})
    yield emit({"type": "start-step"})
    yield emit(_status(mapper.label))

    parent_aiter = result.stream_events().__aiter__()
    parent_task: asyncio.Task[Any] | None = asyncio.create_task(anext(parent_aiter))
    queue_task: asyncio.Task[dict[str, Any] | None] = asyncio.create_task(queue.get())

    try:
        while parent_task is not None:
            done, _ = await asyncio.wait(
                {parent_task, queue_task},
                timeout=8.0,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                idle = time.monotonic() - last_progress
                if idle >= stall_seconds:
                    stalled = True
                    detail = (
                        f"Run stalled for {int(idle)}s with no progress "
                        f"(last status: {mapper.label}). Cancelled so this cannot hang silently."
                    )
                    if workspace is not None:
                        append_error(workspace, detail)
                    cancel = getattr(result, "cancel", None)
                    if callable(cancel):
                        cancel(mode="immediate")
                    raise TimeoutError(detail)
                label = mapper.label
                if idle >= 60:
                    label = f"{mapper.label} · still working ({int(idle)}s, no new events)"
                yield emit(_status(label))
                continue

            if queue_task in done:
                nested = queue_task.result()
                if nested is not None:
                    mark_progress()
                    data = nested.get("data") if isinstance(nested, dict) else None
                    if isinstance(data, dict) and data.get("agentName"):
                        mapper.label = f"Specialist · {data['agentName']} working…"
                    yield emit(nested)
                queue_task = asyncio.create_task(queue.get())

            if parent_task in done:
                try:
                    event = parent_task.result()
                except StopAsyncIteration:
                    parent_task = None
                    continue
                mark_progress()
                for payload in mapper.map_event(event):
                    yield emit(payload)
                parent_task = asyncio.create_task(anext(parent_aiter))

        if not queue_task.done():
            queue_task.cancel()
            try:
                await queue_task
            except asyncio.CancelledError:
                pass

        while True:
            try:
                nested = await asyncio.wait_for(queue.get(), timeout=0.15)
            except TimeoutError:
                break
            if nested is not None:
                yield emit(nested)

    except Exception as exc:  # noqa: BLE001 — surface to UI stream
        detail = str(exc).strip() or exc.__class__.__name__
        if workspace is not None and not stalled:
            append_error(workspace, f"stream failed: {detail}", exc)
        for call_id, name in list(mapper.specialists.items()):
            yield emit(
                {
                    "type": "data-specialist",
                    "data": {
                        "parentToolCallId": call_id,
                        "agentName": name,
                        "kind": "status",
                        "status": "failed",
                        "errorText": detail,
                    },
                    "transient": True,
                }
            )
        yield emit(
            {
                "type": "error",
                "errorText": (
                    f"Run failed: {detail}. "
                    "Partial tool output above may still be useful — send another message. "
                    "Debug: state/ui-stream.jsonl and state/ui-errors.log"
                ),
            }
        )
    finally:
        if parent_task is not None and not parent_task.done():
            parent_task.cancel()
        if not queue_task.done():
            queue_task.cancel()
        reset_specialist_queue(queue_token)

    for payload in mapper.close_parts():
        yield emit(payload)
    yield emit({"type": "finish-step"})
    yield emit({"type": "finish"})
    yield "data: [DONE]\n\n"
