"""Anthropic model pricing (USD per 1M tokens)."""

from __future__ import annotations

MODELS: dict[str, dict[str, float]] = {
    # Current models
    "claude-opus-4-6": {
        "input": 5.00,
        "cache_write": 6.25,
        "cache_read": 0.50,
        "output": 25.00,
    },
    "claude-opus-4-5": {
        "input": 5.00,
        "cache_write": 6.25,
        "cache_read": 0.50,
        "output": 25.00,
    },
    "claude-opus-4-1": {
        "input": 15.00,
        "cache_write": 18.75,
        "cache_read": 1.50,
        "output": 75.00,
    },
    "claude-opus-4": {
        "input": 15.00,
        "cache_write": 18.75,
        "cache_read": 1.50,
        "output": 75.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
        "output": 15.00,
    },
    "claude-sonnet-4-5": {
        "input": 3.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
        "output": 15.00,
    },
    "claude-sonnet-4": {
        "input": 3.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
        "output": 15.00,
    },
    "claude-sonnet-3-7": {
        "input": 3.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
        "output": 15.00,
    },
    "claude-haiku-4-5": {
        "input": 1.00,
        "cache_write": 1.25,
        "cache_read": 0.10,
        "output": 5.00,
    },
    "claude-haiku-3-5": {
        "input": 0.80,
        "cache_write": 1.00,
        "cache_read": 0.08,
        "output": 4.00,
    },
    # Legacy models
    "claude-opus-3": {
        "input": 15.00,
        "cache_write": 18.75,
        "cache_read": 1.50,
        "output": 75.00,
    },
    "claude-haiku-3": {
        "input": 0.25,
        "cache_write": 0.30,
        "cache_read": 0.03,
        "output": 1.25,
    },
    "default": {
        "input": 3.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
        "output": 15.00,
    },
}


def _normalize(s: str) -> str:
    """Lowercase and strip dashes/underscores for fuzzy matching."""
    return s.lower().replace("-", "").replace("_", "")


def get_pricing(model_id: str) -> dict[str, float]:
    """Return pricing dict for a model, using fuzzy substring matching with fallback to default."""
    norm_id = _normalize(model_id)
    for key, pricing in MODELS.items():
        if key == "default":
            continue
        if _normalize(key) in norm_id:
            return pricing
    return MODELS["default"]


def cost_per_token(pricing: dict[str, float]) -> dict[str, float]:
    """Convert per-1M-token prices to per-token prices."""
    return {k: v / 1_000_000 for k, v in pricing.items()}
