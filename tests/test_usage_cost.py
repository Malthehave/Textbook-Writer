"""Model registry pricing + per-book usage ledger."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agents import Agent, Usage
from agents.items import ModelResponse
from openai.types.responses.response_usage import InputTokensDetails, OutputTokensDetails

from textbook_writer.api.stream import stream_agent_run
from textbook_writer.runtime.model_registry import (
    LONG_CONTEXT_INPUT_THRESHOLD,
    estimate_call_cost_usd,
    lookup_model_price,
)
from textbook_writer.runtime.usage_ledger import (
    BookCostHooks,
    load_usage_summary,
    record_model_call,
)


def test_luna_official_short_context_pricing() -> None:
    price = lookup_model_price("gpt-5.6-luna")
    assert price is not None
    assert price.input == 0.20
    assert price.cached_input == 0.02
    assert price.cache_write == 0.25
    assert price.output == 1.20

    cost, priced = estimate_call_cost_usd(
        model_id="gpt-5.6-luna",
        input_tokens=100_000,
        output_tokens=100_000,
        cached_input_tokens=0,
        cache_write_tokens=0,
    )
    assert priced is True
    assert cost == 0.14  # 0.02 input + 0.12 output


def test_luna_cached_and_long_context_pricing() -> None:
    cost, priced = estimate_call_cost_usd(
        model_id="gpt-5.6-luna",
        input_tokens=100_000,
        output_tokens=0,
        cached_input_tokens=40_000,
        cache_write_tokens=10_000,
    )
    assert priced is True
    # uncached 50k @ 0.20, cached 40k @ 0.02, writes 10k @ 0.25
    assert cost == round(0.01 + 0.0008 + 0.0025, 8)

    long_cost, _ = estimate_call_cost_usd(
        model_id="gpt-5.6-luna",
        input_tokens=LONG_CONTEXT_INPUT_THRESHOLD + 1,
        output_tokens=1_000_000,
    )
    assert long_cost is not None
    # long output $1.80/M plus long input on ~272k tokens
    assert long_cost > 1.80


def test_snapshot_alias_and_unknown_model() -> None:
    assert lookup_model_price("gpt-5.6-luna-2026-08-01") is not None
    cost, priced = estimate_call_cost_usd(
        model_id="not-a-real-model",
        input_tokens=100,
        output_tokens=100,
    )
    assert priced is False
    assert cost is None


def test_ledger_accumulates_per_book(tmp_path: Path) -> None:
    book = tmp_path / "book"
    (book / "state").mkdir(parents=True)

    first = record_model_call(
        book,
        agent_name="Textbook manager",
        model_id="gpt-5.6-luna",
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
    )
    second = record_model_call(
        book,
        agent_name="research-architect",
        model_id="gpt-5.6-terra",
        input_tokens=2000,
        output_tokens=1000,
        total_tokens=3000,
    )

    assert first["totals"]["requests"] == 1
    assert second["totals"]["requests"] == 2
    assert second["totals"]["total_tokens"] == 4500
    assert "gpt-5.6-luna" in second["by_model"]
    assert "gpt-5.6-terra" in second["by_model"]
    assert second["totals"]["cost_usd"] > first["totals"]["cost_usd"]

    loaded = load_usage_summary(book)
    assert loaded["totals"]["requests"] == 2
    assert len(loaded["calls"]) == 2


def test_hooks_push_live_updates(tmp_path: Path) -> None:
    book = tmp_path / "book"
    (book / "state").mkdir(parents=True)
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    hooks = BookCostHooks(book_root=book, updates=queue)
    agent = Agent(name="Textbook manager", model="gpt-5.6-luna")
    usage = Usage(
        requests=1,
        input_tokens=10_000,
        output_tokens=2_000,
        total_tokens=12_000,
        input_tokens_details=InputTokensDetails(cached_tokens=1_000, cache_write_tokens=0),
        output_tokens_details=OutputTokensDetails(reasoning_tokens=500),
    )
    response = ModelResponse(output=[], usage=usage, response_id=None, request_id=None)

    async def run() -> dict[str, Any]:
        await hooks.on_llm_end(None, agent, response)  # type: ignore[arg-type]
        return await queue.get()

    update = asyncio.run(run())
    assert update["totals"]["requests"] == 1
    assert update["last_call"]["model"] == "gpt-5.6-luna"
    assert update["last_call"]["priced"] is True
    assert update["totals"]["cost_usd"] > 0


def test_stream_emits_book_cost_data_parts() -> None:
    class FakeRun:
        is_complete = True

        def cancel(self, mode: str = "immediate") -> None:
            del mode

        async def _gen(self):
            if False:
                yield None

        def stream_events(self):
            return self._gen()

    async def main() -> list[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        await queue.put(
            {
                "currency": "USD",
                "pricing_source": "test",
                "totals": {
                    "requests": 1,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                    "cached_input_tokens": 0,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.001,
                    "unpriced_requests": 0,
                },
                "by_model": {},
                "last_call": None,
            }
        )
        payloads: list[dict[str, Any]] = []
        async for chunk in stream_agent_run(
            FakeRun(),
            cost_updates=queue,
            initial_cost={
                "currency": "USD",
                "pricing_source": "test",
                "totals": {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cached_input_tokens": 0,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.0,
                    "unpriced_requests": 0,
                },
                "by_model": {},
                "last_call": None,
            },
        ):
            if chunk.startswith("data: {"):
                payloads.append(json.loads(chunk.removeprefix("data: ").strip()))
        return payloads

    payloads = asyncio.run(main())
    cost_parts = [p for p in payloads if p.get("type") == "data-book-cost"]
    assert len(cost_parts) >= 2
    assert cost_parts[0]["transient"] is True
    assert cost_parts[0]["data"]["totals"]["requests"] == 0
    assert cost_parts[-1]["data"]["totals"]["requests"] == 1
