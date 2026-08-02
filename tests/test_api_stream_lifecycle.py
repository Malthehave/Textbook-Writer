"""Thin Agents SDK → AI SDK UI message stream mapping."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest
from agents import Agent
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent
from fastapi import HTTPException
from openai.types.responses import ResponseTextDeltaEvent

from textbook_writer.api.app import (
    _claim_session_run,
    _stream_session_run,
    active_session_runs,
)
from textbook_writer.api.history import session_items_to_ui_messages
from textbook_writer.api.stream import stream_agent_run
from textbook_writer.api.subagent_events import normalize_subagent_event

AGENT = Agent(name="manager")


def _text_delta(text: str) -> RawResponsesStreamEvent:
    return RawResponsesStreamEvent(
        data=ResponseTextDeltaEvent(
            type="response.output_text.delta",
            delta=text,
            content_index=0,
            item_id="msg_1",
            logprobs=[],
            output_index=0,
            sequence_number=1,
        )
    )


def _tool_call(call_id: str = "call_A", name: str = "chapter-writer") -> RunItemStreamEvent:
    item = ToolCallItem(
        agent=AGENT,
        raw_item={"call_id": call_id, "name": name, "arguments": "{}"},
    )
    return RunItemStreamEvent(name="tool_called", item=item)


def _tool_output(call_id: str = "call_A", output: str = "ok") -> RunItemStreamEvent:
    item = ToolCallOutputItem(
        agent=AGENT,
        raw_item={"call_id": call_id, "output": output},
        output=output,
    )
    return RunItemStreamEvent(name="tool_output", item=item)


class FakeRun:
    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.is_complete = False
        self.cancelled = False

    def cancel(self, mode: str = "immediate") -> None:
        self.cancelled = True

    async def _gen(self):
        for event in self._events:
            yield event
        self.is_complete = True

    def stream_events(self):
        return self._gen()


def _parse_types(chunks: list[str]) -> list[str]:
    types: list[str] = []
    for chunk in chunks:
        if chunk.startswith("data: {") or chunk.startswith("data:{"):
            types.append(json.loads(chunk.removeprefix("data: ").strip())["type"])
    return types


async def _drain(run: FakeRun) -> list[str]:
    chunks: list[str] = []
    async for chunk in stream_agent_run(run):
        chunks.append(chunk)
    return chunks


async def _drain_with_subagent_event(
    run: FakeRun,
    event: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    updates: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    await updates.put(event)
    persisted: list[dict[str, Any]] = []
    chunks: list[str] = []
    async for chunk in stream_agent_run(
        run,
        subagent_updates=updates,
        persist_subagent_events=persisted.extend,
    ):
        chunks.append(chunk)
    return chunks, persisted


def test_text_then_tool_then_output() -> None:
    run = FakeRun(
        [
            _text_delta("Hello"),
            _tool_call(),
            _tool_output(),
            _text_delta("Done"),
        ]
    )
    types = _parse_types(asyncio.run(_drain(run)))
    assert types[0] == "start"
    assert "text-start" in types
    assert "text-delta" in types
    assert types.index("text-end") < types.index("tool-input-start")
    assert "tool-input-available" in types
    assert "tool-output-available" in types
    assert "finish" in types
    assert run.cancelled is False


def test_nested_agent_event_streams_and_persists() -> None:
    event = {
        "outer_tool_call_id": "call_A",
        "agent_name": "Chapter writer",
        "event_type": "assistant-delta",
        "payload": {"text": "Drafting the worked example."},
    }
    chunks, persisted = asyncio.run(
        _drain_with_subagent_event(FakeRun([_text_delta("Manager")]), event)
    )
    payloads = [
        json.loads(chunk.removeprefix("data: ").strip())
        for chunk in chunks
        if chunk.startswith("data: {")
    ]
    nested = [item for item in payloads if item["type"] == "data-subagent-event"]
    assert nested[0]["data"] == event
    assert persisted == [event]


def test_nested_agent_sdk_event_is_normalized() -> None:
    event = normalize_subagent_event(
        {
            "event": _text_delta("Inspecting the chapter."),
            "agent": AGENT,
            "tool_call": {"call_id": "outer-1"},
        }
    )
    assert event == {
        "outer_tool_call_id": "outer-1",
        "agent_name": "manager",
        "event_type": "assistant-delta",
        "payload": {"text": "Inspecting the chapter."},
    }


def test_hosted_nested_tool_gets_a_descriptive_name_and_action() -> None:
    event = normalize_subagent_event(
        {
            "event": SimpleNamespace(
                type="run_item_stream_event",
                name="tool_called",
                item=SimpleNamespace(
                    raw_item={
                        "id": "search-1",
                        "type": "web_search_call",
                        "action": {"query": "distributed RL"},
                    }
                ),
            ),
            "agent": AGENT,
            "tool_call": {"call_id": "outer-1"},
        }
    )
    assert event is not None
    assert event["payload"]["tool_name"] == "web-search"
    assert event["payload"]["input"] == {"query": "distributed RL"}


def test_client_disconnect_cancels_incomplete_run() -> None:
    async def main() -> FakeRun:
        # Never completes: generator keeps the run open until cancelled.
        async def forever():
            yield _text_delta("a")
            await asyncio.sleep(3600)

        run = FakeRun([])
        run.stream_events = lambda: forever()  # type: ignore[method-assign]
        gen = stream_agent_run(run)
        seen = 0
        async for _ in gen:
            seen += 1
            if seen >= 3:
                break
        await gen.aclose()
        return run

    assert asyncio.run(main()).cancelled is True


def test_completed_run_is_not_cancelled_on_teardown() -> None:
    run = FakeRun([_text_delta("hi")])
    asyncio.run(_drain(run))
    assert run.is_complete is True
    assert run.cancelled is False


def test_session_run_is_exclusive_and_released_after_stream() -> None:
    session_id = "session-exclusive"
    active_session_runs.discard(session_id)
    _claim_session_run(session_id)
    try:
        with pytest.raises(HTTPException) as exc_info:
            _claim_session_run(session_id)
        assert exc_info.value.status_code == 409

        async def drain() -> None:
            async for _ in _stream_session_run(FakeRun([_text_delta("done")]), session_id):
                pass

        asyncio.run(drain())
        assert session_id not in active_session_runs
    finally:
        active_session_runs.discard(session_id)


def test_history_keeps_tool_identity_when_prose_interleaves() -> None:
    messages = session_items_to_ui_messages(
        [
            {"role": "user", "content": "write a book"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "research-architect",
                "arguments": '{"q": "rl"}',
            },
            {"role": "assistant", "content": "Kicking off research now."},
            {"type": "function_call_output", "call_id": "call_1", "output": "found 12 sources"},
        ]
    )
    tools = [p for m in messages for p in m["parts"] if p["type"] == "dynamic-tool"]
    assert len(tools) == 1
    assert tools[0]["toolName"] == "research-architect"
    assert tools[0]["state"] == "output-available"
    assert tools[0]["input"] == {"q": "rl"}
    assert tools[0]["output"] == "found 12 sources"
