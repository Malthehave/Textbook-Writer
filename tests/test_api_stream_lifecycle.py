"""Regressions for the API→UI stream audit.

Each test pins one defect that made long runs die or the transcript render
wrong. See stream.py / specialist_stream.py for the reasoning behind each.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest
from agents import Agent
from agents.items import ToolCallItem
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent

from textbook_writer.api.history import session_items_to_ui_messages
from textbook_writer.api.stream import _Mapper, _call_id, _tool_error, stream_agent_run
from textbook_writer.runtime.specialist_stream import _specialist_queue, bind_specialist_queue

AGENT = Agent(name="manager")


def _text_delta(text: str) -> RawResponsesStreamEvent:
    return RawResponsesStreamEvent(
        data=SimpleNamespace(type="response.output_text.delta", delta=text)
    )


def _tool_call(call_id: str = "call_A", name: str = "chapter-writer") -> RunItemStreamEvent:
    item = ToolCallItem(agent=AGENT, raw_item={"call_id": call_id, "name": name, "arguments": "{}"})
    return RunItemStreamEvent(name="tool_called", item=item)


class FakeRun:
    """Stands in for RunResultStreaming."""

    def __init__(self, *, silence: float = 0.0, with_tool: bool = True, events: int = 0) -> None:
        self.silence = silence
        self.with_tool = with_tool
        self.events = events
        self.is_complete = False
        self.cancelled = False

    def cancel(self, mode: str = "immediate") -> None:
        self.cancelled = True

    async def _gen(self):
        if self.with_tool:
            yield _tool_call()
        for i in range(self.events):
            yield _tool_call(call_id=f"call_{i}", name="t")
            await asyncio.sleep(0.01)
        if self.silence:
            await asyncio.sleep(self.silence)
        self.is_complete = True

    def stream_events(self):
        return self._gen()


async def _drain(run: FakeRun, **kwargs: Any) -> list[str]:
    types: list[str] = []
    async for chunk in stream_agent_run(run, poll_seconds=0.1, **kwargs):
        if chunk.startswith("data: {"):
            types.append(json.loads(chunk[6:])["type"])
    return types


def test_specialist_queue_is_visible_to_a_task_created_after_binding() -> None:
    """The run task snapshots context at creation — bind before run_streamed().

    Binding afterwards (the old order) left on_stream looking at an unset
    ContextVar, so every nested specialist event was silently dropped.
    """

    async def main() -> tuple[bool, int]:
        queue: asyncio.Queue = asyncio.Queue()
        bind_specialist_queue(queue)

        async def run_task() -> bool:
            seen = _specialist_queue.get()
            if seen is not None:
                await seen.put({"type": "data-specialist"})
            return seen is not None

        visible = await asyncio.create_task(run_task())
        return visible, queue.qsize()

    visible, delivered = asyncio.run(main())
    assert visible is True
    assert delivered == 1


def test_text_part_closes_at_a_tool_boundary() -> None:
    """Reusing one text id across a tool call reorders the rendered transcript."""

    mapper = _Mapper()
    emitted: list[str] = []
    for chunk in mapper.map_event(_text_delta("Here is the plan.")):
        emitted.append(chunk["type"])
    first_id = mapper.text_id
    for chunk in mapper.map_event(_tool_call()):
        emitted.append(chunk["type"])
    for chunk in mapper.map_event(_text_delta(" And more.")):
        emitted.append(chunk["type"])

    assert emitted.index("text-end") < emitted.index("tool-input-start")
    assert mapper.text_id != first_id


def test_tool_call_is_tracked_as_in_flight_until_output() -> None:
    mapper = _Mapper()
    list(mapper.map_event(_tool_call(call_id="call_A")))
    assert mapper.open_tools == {"call_A"}


@pytest.mark.parametrize(
    "text",
    [
        "Chapter 3: the API returns invalid_request_error when the token limit is exceeded.",
        "Common failure: Error code: 400 means a malformed body.",
    ],
)
def test_tool_error_ignores_error_words_in_legitimate_output(text: str) -> None:
    """A textbook about APIs quotes these strings in successful tool results."""

    assert _tool_error(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "An error occurred while running the tool. Please try again. Error: boom",
        "An error occurred while parsing tool arguments. bad json",
    ],
)
def test_tool_error_still_detects_sdk_failures(text: str) -> None:
    assert _tool_error(text) == text


def test_call_id_fallback_is_stable_for_one_item() -> None:
    """A fresh uuid per read meant a call and its output could never pair up."""

    item = ToolCallItem(agent=AGENT, raw_item={"name": "x", "arguments": "{}"})
    assert _call_id(item) == _call_id(item)


def test_call_id_falls_back_to_item_id() -> None:
    item = ToolCallItem(agent=AGENT, raw_item={"id": "fc_123", "name": "x", "arguments": "{}"})
    assert _call_id(item) == "fc_123"


def test_long_running_tool_is_not_cancelled_as_a_stall() -> None:
    """The parent emits nothing while awaiting a tool — that is not a stall."""

    run = FakeRun(silence=1.2)
    types = asyncio.run(_drain(run, stall_seconds=0.3, tool_stall_seconds=5.0))
    assert run.cancelled is False
    assert "error" not in types
    assert "finish" in types


def test_tool_that_hangs_past_the_generous_bound_still_cancels() -> None:
    run = FakeRun(silence=1.2)
    types = asyncio.run(_drain(run, stall_seconds=0.3, tool_stall_seconds=0.3))
    assert run.cancelled is True
    assert "error" in types


def test_idle_run_with_no_tool_in_flight_still_cancels() -> None:
    run = FakeRun(silence=1.2, with_tool=False)
    types = asyncio.run(_drain(run, stall_seconds=0.3, tool_stall_seconds=5.0))
    assert run.cancelled is True
    assert "error" in types


def test_client_disconnect_cancels_the_underlying_run() -> None:
    """Stop / closed tab must not leave the agent running in the background."""

    async def main() -> FakeRun:
        run = FakeRun(with_tool=False, events=100)
        gen = stream_agent_run(run, poll_seconds=0.1)
        seen = 0
        async for _ in gen:
            seen += 1
            if seen >= 5:
                break
        await gen.aclose()
        return run

    assert asyncio.run(main()).cancelled is True


def test_completed_run_is_not_cancelled_on_teardown() -> None:
    async def main() -> FakeRun:
        run = FakeRun(with_tool=False, events=2)
        async for _ in stream_agent_run(run, poll_seconds=0.1):
            pass
        return run

    assert asyncio.run(main()).cancelled is False


def test_history_keeps_tool_identity_when_prose_interleaves() -> None:
    """A flush used to orphan the output into a nameless card with empty input."""

    messages = session_items_to_ui_messages(
        [
            {"role": "user", "content": "write a book"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "research-scout",
                "arguments": '{"q": "rl"}',
            },
            {"role": "assistant", "content": "Kicking off research now."},
            {"type": "function_call_output", "call_id": "call_1", "output": "found 12 sources"},
        ]
    )
    tools = [p for m in messages for p in m["parts"] if p["type"] == "dynamic-tool"]
    assert len(tools) == 1
    assert tools[0]["toolName"] == "research-scout"
    assert tools[0]["state"] == "output-available"
    assert tools[0]["input"] == {"q": "rl"}
    assert tools[0]["output"] == "found 12 sources"
