"""Thin Agents SDK → AI SDK UI message stream mapping."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from agents import Agent
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent
from openai.types.responses import ResponseTextDeltaEvent

from textbook_writer.api.history import session_items_to_ui_messages
from textbook_writer.api.stream import stream_agent_run

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
