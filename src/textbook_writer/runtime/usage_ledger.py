"""Per-book token/cost ledger + RunHooks that update it after each model call."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents import Agent, RunHooks
from agents.items import ModelResponse
from agents.run_context import RunContextWrapper

from textbook_writer.runtime.model_registry import (
    LONG_CONTEXT_INPUT_THRESHOLD,
    PRICING_SOURCE,
    estimate_call_cost_usd,
)

USAGE_FILENAME = "usage.json"
_MAX_CALL_HISTORY = 1000


def usage_path(book_root: str | Path) -> Path:
    return Path(book_root) / "state" / USAGE_FILENAME


def empty_usage_summary() -> dict[str, Any]:
    return {
        "currency": "USD",
        "pricing_source": PRICING_SOURCE,
        "totals": _empty_totals(),
        "by_model": {},
        "calls": [],
    }


def _empty_totals() -> dict[str, Any]:
    return {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "cost_usd": 0.0,
        "unpriced_requests": 0,
    }


def load_usage_summary(book_root: str | Path) -> dict[str, Any]:
    path = usage_path(book_root)
    if not path.is_file():
        return empty_usage_summary()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return empty_usage_summary()
    summary = empty_usage_summary()
    summary.update({k: raw.get(k, summary[k]) for k in summary})
    totals = _empty_totals()
    totals.update(raw.get("totals") or {})
    summary["totals"] = totals
    summary["by_model"] = dict(raw.get("by_model") or {})
    summary["calls"] = list(raw.get("calls") or [])
    return summary


def resolve_model_id(model: Any) -> str:
    if isinstance(model, str) and model.strip():
        return model.strip()
    for attr in ("model", "model_name", "name"):
        value = getattr(model, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(model)


def _token_details(usage: Any) -> tuple[int, int, int, int, int]:
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens))
    input_details = getattr(usage, "input_tokens_details", None)
    cached = int(getattr(input_details, "cached_tokens", 0) or 0)
    writes = int(getattr(input_details, "cache_write_tokens", 0) or 0)
    return input_tokens, output_tokens, total_tokens, cached, writes


def _add_into(bucket: dict[str, Any], call: dict[str, Any]) -> None:
    bucket["requests"] = int(bucket.get("requests", 0)) + 1
    bucket["input_tokens"] = int(bucket.get("input_tokens", 0)) + int(call["input_tokens"])
    bucket["output_tokens"] = int(bucket.get("output_tokens", 0)) + int(call["output_tokens"])
    bucket["total_tokens"] = int(bucket.get("total_tokens", 0)) + int(call["total_tokens"])
    bucket["cached_input_tokens"] = int(bucket.get("cached_input_tokens", 0)) + int(
        call["cached_input_tokens"]
    )
    bucket["cache_write_tokens"] = int(bucket.get("cache_write_tokens", 0)) + int(
        call["cache_write_tokens"]
    )
    if call.get("priced") and call.get("cost_usd") is not None:
        bucket["cost_usd"] = round(float(bucket.get("cost_usd", 0.0)) + float(call["cost_usd"]), 8)
    else:
        bucket["unpriced_requests"] = int(bucket.get("unpriced_requests", 0)) + 1


def record_model_call(
    book_root: str | Path,
    *,
    agent_name: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> dict[str, Any]:
    """Append one priced call to the book ledger and return a UI-ready summary."""

    cost_usd, priced = estimate_call_cost_usd(
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    call = {
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "agent": agent_name,
        "model": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_write_tokens": cache_write_tokens,
        "long_context": input_tokens > LONG_CONTEXT_INPUT_THRESHOLD,
        "cost_usd": cost_usd,
        "priced": priced,
    }

    path = usage_path(book_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = load_usage_summary(book_root)
    _add_into(summary["totals"], call)
    model_bucket = summary["by_model"].setdefault(model_id, _empty_totals())
    _add_into(model_bucket, call)
    summary["by_model"][model_id] = model_bucket
    calls = list(summary["calls"])
    calls.append(call)
    summary["calls"] = calls[-_MAX_CALL_HISTORY:]
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "currency": "USD",
        "pricing_source": PRICING_SOURCE,
        "totals": summary["totals"],
        "by_model": summary["by_model"],
        "last_call": call,
    }


class BookCostHooks(RunHooks[Any]):
    """Record priced usage after every LLM call and push live UI updates."""

    def __init__(
        self,
        *,
        book_root: str | Path,
        updates: asyncio.Queue[dict[str, Any]] | None = None,
    ) -> None:
        self.book_root = Path(book_root)
        self.updates = updates

    def snapshot(self) -> dict[str, Any]:
        summary = load_usage_summary(self.book_root)
        return {
            "currency": summary["currency"],
            "pricing_source": summary["pricing_source"],
            "totals": summary["totals"],
            "by_model": summary["by_model"],
            "last_call": summary["calls"][-1] if summary["calls"] else None,
        }

    async def on_llm_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        response: ModelResponse,
    ) -> None:
        del context  # usage is on the response; ledger is authoritative for the book
        usage = response.usage
        input_tokens, output_tokens, total_tokens, cached, writes = _token_details(usage)
        if total_tokens <= 0 and input_tokens <= 0 and output_tokens <= 0:
            return
        update = record_model_call(
            self.book_root,
            agent_name=getattr(agent, "name", None) or "agent",
            model_id=resolve_model_id(getattr(agent, "model", None)),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cached_input_tokens=cached,
            cache_write_tokens=writes,
        )
        if self.updates is not None:
            await self.updates.put(update)
