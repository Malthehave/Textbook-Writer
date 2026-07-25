from textbook_writer.api.history import session_items_to_ui_messages


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
