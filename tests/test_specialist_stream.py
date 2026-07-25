from types import SimpleNamespace

from textbook_writer.runtime.specialist_stream import (
    is_specialist_tool,
    nested_event_chunks,
)


def test_is_specialist_tool_names() -> None:
    assert is_specialist_tool("chapter-writer")
    assert is_specialist_tool("research-scout")
    assert not is_specialist_tool("acquire_and_freeze")
    assert not is_specialist_tool("save_stage_artifact")


def test_nested_text_delta_chunks() -> None:
    tool_call = SimpleNamespace(name="chapter-writer", call_id="call_abc")
    event = SimpleNamespace(
        data=SimpleNamespace(type="response.output_text.delta", delta="Hello")
    )
    # RawResponsesStreamEvent-like payload via duck typing in nested_event_chunks
    from agents.stream_events import RawResponsesStreamEvent

    payload = {
        "event": RawResponsesStreamEvent(data=event.data),
        "agent": SimpleNamespace(name="Chapter writer"),
        "tool_call": tool_call,
    }
    chunks = nested_event_chunks(payload)  # type: ignore[arg-type]
    assert len(chunks) == 1
    assert chunks[0]["type"] == "data-specialist"
    assert chunks[0]["transient"] is True
    assert chunks[0]["data"]["kind"] == "text-delta"
    assert chunks[0]["data"]["text"] == "Hello"
    assert chunks[0]["data"]["parentToolCallId"] == "call_abc"
    assert chunks[0]["data"]["agentName"] == "chapter-writer"
