"""Compute cost metrics and efficiency scores for sessions."""

from __future__ import annotations

from dataclasses import dataclass, field

from .parser import Session, TurnUsage
from .pricing import cost_per_token, get_pricing


@dataclass
class TurnMetrics:
    turn: TurnUsage
    actual_cost: float
    cost_no_cache: float
    cache_write_overhead: float

    @property
    def savings(self) -> float:
        return self.cost_no_cache - self.actual_cost

    @property
    def net_savings(self) -> float:
        return self.savings - self.cache_write_overhead

    @property
    def savings_pct(self) -> float:
        if self.cost_no_cache == 0:
            return 0.0
        return self.savings / self.cost_no_cache * 100


@dataclass
class SessionMetrics:
    session: Session
    turns: list[TurnMetrics] = field(default_factory=list)

    @property
    def actual_cost(self) -> float:
        return sum(t.actual_cost for t in self.turns)

    @property
    def cost_no_cache(self) -> float:
        return sum(t.cost_no_cache for t in self.turns)

    @property
    def cache_write_overhead(self) -> float:
        return sum(t.cache_write_overhead for t in self.turns)

    @property
    def savings(self) -> float:
        return self.cost_no_cache - self.actual_cost

    @property
    def net_savings(self) -> float:
        return self.savings - self.cache_write_overhead

    @property
    def savings_pct(self) -> float:
        if self.cost_no_cache == 0:
            return 0.0
        return self.savings / self.cost_no_cache * 100

    @property
    def hit_rate(self) -> float:
        return self.session.hit_rate

    @property
    def cache_efficiency_score(self) -> float:
        total_input = self.session.total_input
        total_cacheable = self.session.total_cacheable
        denom = total_input + total_cacheable
        if denom == 0:
            return 0.0
        return self.hit_rate * (total_cacheable / denom)

    def grade(self) -> str:
        score = self.cache_efficiency_score
        if score >= 0.70:
            return "A"
        if score >= 0.50:
            return "B"
        if score >= 0.30:
            return "C"
        if score >= 0.10:
            return "D"
        return "F"


def _compute_turn_metrics(turn: TurnUsage) -> TurnMetrics:
    pricing = get_pricing(turn.model)
    ppt = cost_per_token(pricing)

    s = turn.cacheable_tokens
    h = turn.hit_rate
    d = turn.input_tokens
    o = turn.output_tokens

    # Actual cost: C = S * [(1-h)*P_miss + h*P_hit] + D*P_miss + O*P_out
    # But actual_cost should reflect what was actually charged, including cache_write pricing
    # cache_creation tokens are charged at cache_write rate, cache_read at cache_read rate,
    # input_tokens at input rate, output at output rate
    actual_cost = (
        turn.cache_creation_tokens * ppt["cache_write"]
        + turn.cache_read_tokens * ppt["cache_read"]
        + d * ppt["input"]
        + o * ppt["output"]
    )

    # Baseline without cache: all input tokens at normal input price
    cost_no_cache = (s + d) * ppt["input"] + o * ppt["output"]

    # Overhead: cache_write is more expensive than regular input
    cache_write_overhead = turn.cache_creation_tokens * (ppt["cache_write"] - ppt["input"])

    return TurnMetrics(
        turn=turn,
        actual_cost=actual_cost,
        cost_no_cache=cost_no_cache,
        cache_write_overhead=cache_write_overhead,
    )


def compute_session_metrics(session: Session) -> SessionMetrics:
    turn_metrics = [_compute_turn_metrics(t) for t in session.turns]
    return SessionMetrics(session=session, turns=turn_metrics)


def aggregate(sessions_metrics: list[SessionMetrics]) -> dict:
    """Compute aggregate statistics across all sessions."""
    if not sessions_metrics:
        return {
            "total_actual_cost": 0.0,
            "total_cost_no_cache": 0.0,
            "total_savings": 0.0,
            "total_net_savings": 0.0,
            "avg_hit_rate": 0.0,
            "avg_efficiency_score": 0.0,
            "best_session": None,
            "worst_session": None,
        }

    total_actual = sum(sm.actual_cost for sm in sessions_metrics)
    total_no_cache = sum(sm.cost_no_cache for sm in sessions_metrics)
    total_savings = total_no_cache - total_actual
    total_overhead = sum(sm.cache_write_overhead for sm in sessions_metrics)
    total_net = total_savings - total_overhead
    avg_hit = sum(sm.hit_rate for sm in sessions_metrics) / len(sessions_metrics)
    avg_eff = sum(sm.cache_efficiency_score for sm in sessions_metrics) / len(sessions_metrics)

    best = max(sessions_metrics, key=lambda s: s.cache_efficiency_score)
    worst = min(sessions_metrics, key=lambda s: s.cache_efficiency_score)

    return {
        "total_actual_cost": total_actual,
        "total_cost_no_cache": total_no_cache,
        "total_savings": total_savings,
        "total_net_savings": total_net,
        "avg_hit_rate": avg_hit,
        "avg_efficiency_score": avg_eff,
        "best_session": best,
        "worst_session": worst,
    }
