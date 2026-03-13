"""Tests for pricing module."""

from claude_cache_analyzer.pricing import MODELS, cost_per_token, get_pricing


def test_get_pricing_exact_match():
    pricing = get_pricing("claude-sonnet-4")
    assert pricing == MODELS["claude-sonnet-4"]


def test_get_pricing_fuzzy_match():
    # Full model ID with date suffix should match base model
    pricing = get_pricing("claude-sonnet-4-20250514")
    assert pricing == MODELS["claude-sonnet-4"]

    pricing = get_pricing("claude-opus-4-20250514")
    assert pricing == MODELS["claude-opus-4"]

    pricing = get_pricing("claude-haiku-3-5-20250101")
    assert pricing == MODELS["claude-haiku-3-5"]

    # New models
    pricing = get_pricing("claude-opus-4-6-20260101")
    assert pricing == MODELS["claude-opus-4-6"]
    assert pricing["input"] == 5.00

    pricing = get_pricing("claude-opus-4-5-20251101")
    assert pricing == MODELS["claude-opus-4-5"]
    assert pricing["input"] == 5.00

    pricing = get_pricing("claude-opus-4-1-20250805")
    assert pricing == MODELS["claude-opus-4-1"]
    assert pricing["input"] == 15.00

    pricing = get_pricing("claude-sonnet-4-6-20260101")
    assert pricing == MODELS["claude-sonnet-4-6"]

    pricing = get_pricing("claude-sonnet-4-5-20250929")
    assert pricing == MODELS["claude-sonnet-4-5"]

    pricing = get_pricing("claude-haiku-4-5-20251001")
    assert pricing == MODELS["claude-haiku-4-5"]
    assert pricing["input"] == 1.00


def test_get_pricing_unknown_model_fallback():
    pricing = get_pricing("some-unknown-model-xyz")
    assert pricing == MODELS["default"]


def test_cost_per_token():
    pricing = {"input": 3.00, "cache_write": 3.75, "cache_read": 0.30, "output": 15.00}
    ppt = cost_per_token(pricing)
    assert ppt["input"] == 3.00 / 1_000_000
    assert ppt["cache_write"] == 3.75 / 1_000_000
    assert ppt["cache_read"] == 0.30 / 1_000_000
    assert ppt["output"] == 15.00 / 1_000_000
