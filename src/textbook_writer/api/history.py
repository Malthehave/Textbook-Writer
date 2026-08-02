"""Agents SDK session items → AI SDK UIMessage shapes."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
                continue
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"output_text", "text", "input_text"} and part.get("text"):
                chunks.append(str(part["text"]))
            elif isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "".join(chunks)
    return ""


def _parse_args(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    return raw if raw is not None else {}


def session_items_to_ui_messages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse Agents SDK session items into simple UI messages for the chat panel."""

    messages: list[dict[str, Any]] = []
    pending_tools: dict[str, dict[str, Any]] = {}
    tool_parts: dict[str, dict[str, Any]] = {}

    def flush_assistant_tools() -> None:
        if not pending_tools:
            return
        parts = list(pending_tools.values())
        pending_tools.clear()
        messages.append(
            {"id": f"msg_{uuid4().hex}", "role": "assistant", "parts": parts}
        )

    for item in items:
        role = item.get("role")
        item_type = item.get("type")

        if role == "user":
            flush_assistant_tools()
            text = _text_from_content(item.get("content"))
            if not text.strip():
                continue
            messages.append(
                {
                    "id": f"msg_{uuid4().hex}",
                    "role": "user",
                    "parts": [{"type": "text", "text": text}],
                }
            )
            continue

        if role == "assistant":
            flush_assistant_tools()
            text = _text_from_content(item.get("content"))
            if not text.strip():
                continue
            messages.append(
                {
                    "id": f"msg_{uuid4().hex}",
                    "role": "assistant",
                    "parts": [{"type": "text", "text": text}],
                }
            )
            continue

        if item_type == "function_call":
            call_id = str(item.get("call_id") or item.get("id") or uuid4().hex)
            part = {
                "type": "dynamic-tool",
                "toolCallId": call_id,
                "toolName": str(item.get("name") or "tool"),
                "state": "input-available",
                "input": _parse_args(item.get("arguments")),
            }
            pending_tools[call_id] = part
            tool_parts[call_id] = part
            continue

        if item_type == "function_call_output":
            call_id = str(item.get("call_id") or "")
            part = tool_parts.get(call_id)
            if part is None:
                part = {
                    "type": "dynamic-tool",
                    "toolCallId": call_id or f"call_{uuid4().hex[:12]}",
                    "toolName": "tool",
                    "state": "output-available",
                    "input": {},
                }
                pending_tools[part["toolCallId"]] = part
                tool_parts[part["toolCallId"]] = part
            part["state"] = "output-available"
            part["output"] = item.get("output", "")
            continue

    flush_assistant_tools()
    return messages
