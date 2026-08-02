"""Normalize nested agent streams for persistence and UI display."""

from __future__ import annotations

import json
from typing import Any

from openai.types.responses import (
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseTextDeltaEvent,
)

TOOL_TYPE_NAMES = {
    "web_search_call": "web-search",
    "file_search_call": "file-search",
    "computer_call": "computer",
    "local_shell_call": "shell",
    "code_interpreter_call": "code-interpreter",
    "mcp_call": "mcp",
}


def _value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _call_id(item: Any) -> str:
    return str(_value(item, "call_id") or _value(item, "id") or "")


def _tool_name(item: Any) -> str:
    name = _value(item, "name")
    if name:
        return str(name)
    item_type = str(_value(item, "type") or "")
    return TOOL_TYPE_NAMES.get(item_type, item_type.replace("_call", "").replace("_", "-") or "tool")


def _tool_arguments(item: Any) -> Any:
    arguments = _value(item, "arguments")
    if arguments is None:
        arguments = _value(item, "action")
    if arguments is None:
        arguments = _value(item, "input")
    if not isinstance(arguments, str):
        if hasattr(arguments, "model_dump"):
            return arguments.model_dump(mode="json")
        return arguments if arguments is not None else {}
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return arguments


def normalize_subagent_event(stream_event: Any) -> dict[str, Any] | None:
    event = stream_event.get("event")
    agent = stream_event.get("agent")
    outer_tool_call = stream_event.get("tool_call")
    outer_tool_call_id = _call_id(outer_tool_call)
    if not outer_tool_call_id:
        return None

    base = {
        "outer_tool_call_id": outer_tool_call_id,
        "agent_name": str(getattr(agent, "name", None) or "Specialist"),
    }
    event_type = getattr(event, "type", None)
    if event_type == "raw_response_event":
        data = event.data
        if isinstance(data, ResponseTextDeltaEvent):
            return {
                **base,
                "event_type": "assistant-delta",
                "payload": {"text": data.delta},
            }
        if isinstance(
            data,
            (ResponseReasoningSummaryTextDeltaEvent, ResponseReasoningTextDeltaEvent),
        ):
            return {
                **base,
                "event_type": "reasoning-delta",
                "payload": {"text": data.delta},
            }
        return None

    if event_type != "run_item_stream_event":
        return None
    name = getattr(event, "name", None)
    item = getattr(event, "item", None)
    raw = getattr(item, "raw_item", item)
    if name == "tool_called":
        return {
            **base,
            "event_type": "tool-called",
            "payload": {
                "tool_call_id": _call_id(raw),
                "tool_name": _tool_name(raw),
                "input": _tool_arguments(raw),
            },
        }
    if name == "tool_output":
        output = getattr(item, "output", None)
        if output is None:
            output = _value(raw, "output") or _value(raw, "result") or ""
        return {
            **base,
            "event_type": "tool-output",
            "payload": {
                "tool_call_id": _call_id(raw),
                "output": output,
            },
        }
    return None


def coalesce_subagent_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coalesced: list[dict[str, Any]] = []
    for event in events:
        if (
            coalesced
            and event["event_type"] in {"assistant-delta", "reasoning-delta"}
            and event["event_type"] == coalesced[-1]["event_type"]
            and event["outer_tool_call_id"] == coalesced[-1]["outer_tool_call_id"]
            and event["agent_name"] == coalesced[-1]["agent_name"]
        ):
            coalesced[-1]["payload"]["text"] += event["payload"]["text"]
        else:
            coalesced.append(event)
    return coalesced
