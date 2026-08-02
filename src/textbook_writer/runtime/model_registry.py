"""Official OpenAI API model pricing for cost tracking.

Rates from https://developers.openai.com/api/docs/pricing (standard tier).
Amounts are USD per 1M tokens. Long-context rates apply to the full request
when input tokens exceed ``LONG_CONTEXT_INPUT_THRESHOLD``.
"""

from __future__ import annotations

from dataclasses import dataclass

# Prompts with >272K input tokens use long-context rates for the whole request.
LONG_CONTEXT_INPUT_THRESHOLD = 272_000


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Per-1M-token USD rates for one model (standard processing)."""

    input: float
    cached_input: float
    output: float
    cache_write: float | None = None
    long_input: float | None = None
    long_cached_input: float | None = None
    long_output: float | None = None
    long_cache_write: float | None = None

    def rates_for(self, *, input_tokens: int) -> tuple[float, float, float, float | None]:
        """Return (input, cached_input, output, cache_write) for this request size."""

        long = input_tokens > LONG_CONTEXT_INPUT_THRESHOLD
        if not long:
            return self.input, self.cached_input, self.output, self.cache_write
        return (
            self.long_input if self.long_input is not None else self.input,
            self.long_cached_input
            if self.long_cached_input is not None
            else self.cached_input,
            self.long_output if self.long_output is not None else self.output,
            self.long_cache_write
            if self.long_cache_write is not None
            else self.cache_write,
        )


# GPT-5.6 family — standard short / long context (developers.openai.com/api/docs/pricing).
MODEL_REGISTRY: dict[str, ModelPrice] = {
    "gpt-5.6-sol": ModelPrice(
        input=5.00,
        cached_input=0.50,
        cache_write=6.25,
        output=30.00,
        long_input=10.00,
        long_cached_input=1.00,
        long_cache_write=12.50,
        long_output=45.00,
    ),
    "gpt-5.6-terra": ModelPrice(
        input=2.00,
        cached_input=0.20,
        cache_write=2.50,
        output=12.00,
        long_input=4.00,
        long_cached_input=0.40,
        long_cache_write=5.00,
        long_output=18.00,
    ),
    "gpt-5.6-luna": ModelPrice(
        input=0.20,
        cached_input=0.02,
        cache_write=0.25,
        output=1.20,
        long_input=0.40,
        long_cached_input=0.04,
        long_cache_write=0.50,
        long_output=1.80,
    ),
}

PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"
DEFAULT_MODEL = "gpt-5.6-luna"


def lookup_model_price(model_id: str) -> ModelPrice | None:
    """Return registry pricing for ``model_id``, stripping date snapshots when needed."""

    key = model_id.strip()
    if key in MODEL_REGISTRY:
        return MODEL_REGISTRY[key]
    # Snapshots look like gpt-5.6-luna-2026-08-01 — match the longest registered prefix.
    for registered in sorted(MODEL_REGISTRY, key=len, reverse=True):
        if key.startswith(f"{registered}-") or key.startswith(f"{registered}."):
            return MODEL_REGISTRY[registered]
    return None


def estimate_call_cost_usd(
    *,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> tuple[float | None, bool]:
    """Estimate USD cost for one model call.

    Returns ``(cost_usd, priced)``. When the model is unknown, ``priced`` is False
    and ``cost_usd`` is None.
    """

    price = lookup_model_price(model_id)
    if price is None:
        return None, False

    cached = max(0, cached_input_tokens)
    writes = max(0, cache_write_tokens)
    uncached = max(0, input_tokens - cached - writes)
    input_rate, cached_rate, output_rate, write_rate = price.rates_for(
        input_tokens=input_tokens
    )

    cost = (
        (uncached / 1_000_000.0) * input_rate
        + (cached / 1_000_000.0) * cached_rate
        + (output_tokens / 1_000_000.0) * output_rate
    )
    if write_rate is not None and writes:
        cost += (writes / 1_000_000.0) * write_rate
    return round(cost, 8), True
