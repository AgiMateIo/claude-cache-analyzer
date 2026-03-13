"""Tests for metrics module."""

from pathlib import Path

from claude_cache_analyzer.metrics import SessionMetrics, compute_session_metrics
from claude_cache_analyzer.parser import Session, TurnUsage
from claude_cache_analyzer.pricing import cost_per_token, get_pricing


def _make_session(turns: list[TurnUsage]) -> Session:
    return Session(session_id="test", project="test-proj", path=Path("/tmp/test.jsonl"), turns=turns)


def _make_turn(
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation: int = 0,
    cache_read: int = 0,
    model: str = "claude-sonnet-4-20250514",
) -> TurnUsage:
    return TurnUsage(
        timestamp=None,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation,
        cache_read_tokens=cache_read,
    )


def test_actual_cost_formula():
    turn = _make_turn(input_tokens=1000, output_tokens=200, cache_creation=5000, cache_read=3000)
    pricing = get_pricing(turn.model)
    ppt = cost_per_token(pricing)

    session = _make_session([turn])
    sm = compute_session_metrics(session)
    tm = sm.turns[0]

    expected = (
        5000 * ppt["cache_write"]
        + 3000 * ppt["cache_read"]
        + 1000 * ppt["input"]
        + 200 * ppt["output"]
    )
    assert abs(tm.actual_cost - expected) < 1e-12


def test_cost_no_cache_formula():
    turn = _make_turn(input_tokens=1000, output_tokens=200, cache_creation=5000, cache_read=3000)
    pricing = get_pricing(turn.model)
    ppt = cost_per_token(pricing)

    session = _make_session([turn])
    sm = compute_session_metrics(session)
    tm = sm.turns[0]

    # Without cache: all cacheable + input at input price
    expected = (8000 + 1000) * ppt["input"] + 200 * ppt["output"]
    assert abs(tm.cost_no_cache - expected) < 1e-12


def test_savings_positive_for_high_hit_rate():
    # 100% hit rate — all from cache
    turn = _make_turn(input_tokens=100, output_tokens=50, cache_creation=0, cache_read=10000)
    session = _make_session([turn])
    sm = compute_session_metrics(session)

    assert sm.savings > 0
    assert sm.savings_pct > 0
    # No cache_write overhead since cache_creation=0
    assert sm.cache_write_overhead == 0
    assert sm.net_savings == sm.savings


def test_grade_boundaries():
    # High efficiency → A
    turn_a = _make_turn(input_tokens=100, output_tokens=10, cache_creation=0, cache_read=50000)
    sm_a = compute_session_metrics(_make_session([turn_a]))
    assert sm_a.cache_efficiency_score >= 0.70
    assert sm_a.grade() == "A"

    # No cache at all → F
    turn_f = _make_turn(input_tokens=1000, output_tokens=100, cache_creation=0, cache_read=0)
    sm_f = compute_session_metrics(_make_session([turn_f]))
    assert sm_f.cache_efficiency_score == 0.0
    assert sm_f.grade() == "F"

    # Medium — mostly read, some dynamic
    turn_c = _make_turn(input_tokens=5000, output_tokens=100, cache_creation=2000, cache_read=3000)
    sm_c = compute_session_metrics(_make_session([turn_c]))
    score = sm_c.cache_efficiency_score
    grade = sm_c.grade()
    # Verify grade matches score
    if score >= 0.70:
        assert grade == "A"
    elif score >= 0.50:
        assert grade == "B"
    elif score >= 0.30:
        assert grade == "C"
    elif score >= 0.10:
        assert grade == "D"
    else:
        assert grade == "F"


def test_session_metrics_aggregation():
    turn1 = _make_turn(input_tokens=500, output_tokens=100, cache_creation=3000, cache_read=7000)
    turn2 = _make_turn(input_tokens=200, output_tokens=50, cache_creation=0, cache_read=9000)
    session = _make_session([turn1, turn2])
    sm = compute_session_metrics(session)

    assert sm.actual_cost == sum(t.actual_cost for t in sm.turns)
    assert sm.cost_no_cache == sum(t.cost_no_cache for t in sm.turns)
    assert abs(sm.savings - (sm.cost_no_cache - sm.actual_cost)) < 1e-12
