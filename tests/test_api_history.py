from pathlib import Path

from textbook_writer.api.history import session_items_to_ui_messages
from textbook_writer.api.store import SessionStore


def test_session_items_to_ui_messages_collapses_tools() -> None:
    messages = session_items_to_ui_messages(
        [
            {"role": "user", "content": "Build a book"},
            {
                "type": "function_call",
                "name": "research_scout",
                "call_id": "c1",
                "arguments": '{"topic":"algebra"}',
            },
            {"type": "function_call_output", "call_id": "c1", "output": "done"},
            {"role": "assistant", "content": "Research finished."},
        ]
    )
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[0]["parts"][0]["text"] == "Build a book"
    assert messages[1]["role"] == "assistant"
    tool = messages[1]["parts"][0]
    assert tool["toolName"] == "research_scout"
    assert tool["state"] == "output-available"
    assert tool["output"] == "done"
    assert messages[2]["parts"][0]["text"] == "Research finished."


def test_subagent_transcript_is_persisted_and_restored(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite")
    store.create(session_id="session-1")
    event = {
        "outer_tool_call_id": "c1",
        "agent_name": "Research architect",
        "event_type": "assistant-delta",
        "payload": {"text": "Checking primary sources."},
    }
    store.append_subagent_events("session-1", [event])
    saved = store.list_subagent_events("session-1")
    assert saved[0]["payload"]["text"] == "Checking primary sources."

    messages = session_items_to_ui_messages(
        [
            {
                "type": "function_call",
                "name": "research-architect",
                "call_id": "c1",
                "arguments": '{"input":"research"}',
            },
            {"type": "function_call_output", "call_id": "c1", "output": "done"},
        ],
        subagent_events=saved,
    )
    transcript = messages[0]["parts"][1]
    assert transcript["type"] == "data-subagent-event"
    assert transcript["data"]["outer_tool_call_id"] == "c1"
