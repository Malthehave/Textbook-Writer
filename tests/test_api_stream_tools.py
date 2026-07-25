from types import SimpleNamespace

from agents.items import ToolCallItem

from textbook_writer.api.stream import _call_id, _tool_start


def test_call_id_uses_call_id_not_item_id() -> None:
    raw = SimpleNamespace(call_id="call_77d33103d876", id="fc_should_not_win", name="t")
    item = object.__new__(ToolCallItem)
    item.raw_item = raw  # type: ignore[attr-defined]
    assert _call_id(item) == "call_77d33103d876"


def test_call_id_from_dict_raw() -> None:
    item = object.__new__(ToolCallItem)
    item.raw_item = {"call_id": "call_abc", "id": "fc_xyz", "name": "t"}  # type: ignore[attr-defined]
    assert _call_id(item) == "call_abc"


def test_tool_start_marks_dynamic() -> None:
    chunks = _tool_start("call_1", "research-scout", {"q": 1})
    assert chunks[0]["type"] == "tool-input-start"
    assert chunks[0]["dynamic"] is True
    assert chunks[1]["toolCallId"] == "call_1"
