"""Rich terminal output for cache efficiency reports."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .metrics import SessionMetrics, aggregate

console = Console()

GRADE_COLORS = {
    "A": "green",
    "B": "cyan",
    "C": "yellow",
    "D": "red",
    "F": "red",
}


def _fmt_cost(v: float) -> str:
    return f"${v:.4f}"


def _fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


def _fmt_tokens(v: int) -> str:
    return f"{v:,}"


def _grade_text(grade: str) -> Text:
    return Text(grade, style=f"bold {GRADE_COLORS.get(grade, 'white')}")


def _hit_rate_bar(rate: float, width: int = 20) -> Text:
    filled = int(rate * width)
    empty = width - filled
    bar = Text()
    bar.append("█" * filled, style="green")
    bar.append("░" * empty, style="dim")
    bar.append(f" {rate * 100:.1f}%")
    return bar


def print_project_report(
    sessions_metrics: list[SessionMetrics], project_name: str
) -> None:
    """Print the full cache efficiency report."""
    agg = aggregate(sessions_metrics)

    # 1. Header
    n = len(sessions_metrics)
    header = Text.assemble(
        ("   Claude Code · Cache Efficiency Report\n", "bold white"),
        (f"   Project: {project_name}  ·  {n} sessions analysed", "dim"),
    )
    console.print(Panel(header, style="bold blue", expand=False))
    console.print()

    # 2. Summary table
    summary = Table(title="Summary", show_header=True, header_style="bold magenta")
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")

    summary.add_row("Total actual cost", _fmt_cost(agg["total_actual_cost"]))
    summary.add_row("Cost without cache", _fmt_cost(agg["total_cost_no_cache"]))
    summary.add_row("Total savings", _fmt_cost(agg["total_savings"]))
    summary.add_row(
        "Net savings (after write overhead)", _fmt_cost(agg["total_net_savings"])
    )
    if agg["total_cost_no_cache"] > 0:
        savings_pct = agg["total_savings"] / agg["total_cost_no_cache"] * 100
    else:
        savings_pct = 0.0
    summary.add_row("Savings %", _fmt_pct(savings_pct))
    summary.add_row("Avg cache hit rate", _fmt_pct(agg["avg_hit_rate"] * 100))
    summary.add_row("Avg efficiency score", f"{agg['avg_efficiency_score']:.2f}")

    console.print(summary)
    console.print()

    # 3. Sessions table
    sessions_table = Table(
        title="Sessions", show_header=True, header_style="bold cyan"
    )
    sessions_table.add_column("#", justify="right", style="dim", width=4)
    sessions_table.add_column("Session ID", width=10)
    sessions_table.add_column("Date", width=18)
    sessions_table.add_column("Turns", justify="right", width=6)
    sessions_table.add_column("Model", width=20)
    sessions_table.add_column("Input tok", justify="right", width=12)
    sessions_table.add_column("Cache hit%", width=28)
    sessions_table.add_column("Efficiency", justify="right", width=10)
    sessions_table.add_column("Grade", justify="center", width=6)
    sessions_table.add_column("Actual $", justify="right", width=10)
    sessions_table.add_column("Savings $", justify="right", width=10)
    sessions_table.add_column("Savings %", justify="right", width=10)

    for i, sm in enumerate(sessions_metrics, 1):
        sess = sm.session
        started = sess.started_at
        date_str = started.strftime("%Y-%m-%d %H:%M") if started else "—"
        total_in = sess.total_input + sess.total_cacheable

        sessions_table.add_row(
            str(i),
            sess.session_id[:8],
            date_str,
            str(sess.num_turns),
            sess.model,
            _fmt_tokens(total_in),
            _hit_rate_bar(sm.hit_rate),
            f"{sm.cache_efficiency_score:.2f}",
            _grade_text(sm.grade()),
            _fmt_cost(sm.actual_cost),
            _fmt_cost(sm.savings),
            _fmt_pct(sm.savings_pct),
        )

    console.print(sessions_table)
    console.print()

    # 4. Top 3 / Bottom 3
    if len(sessions_metrics) >= 2:
        sorted_by_eff = sorted(
            sessions_metrics, key=lambda s: s.cache_efficiency_score, reverse=True
        )

        top3 = sorted_by_eff[:3]
        bottom3 = sorted_by_eff[-3:]

        top_table = Table(title="🏆 Top 3", show_header=True, header_style="bold green")
        top_table.add_column("Session ID", width=10)
        top_table.add_column("Efficiency", justify="right")
        top_table.add_column("Grade", justify="center")
        top_table.add_column("Savings", justify="right")

        for sm in top3:
            top_table.add_row(
                sm.session.session_id[:8],
                f"{sm.cache_efficiency_score:.2f}",
                _grade_text(sm.grade()),
                _fmt_cost(sm.savings),
            )

        bottom_table = Table(
            title="⚠️  Bottom 3", show_header=True, header_style="bold red"
        )
        bottom_table.add_column("Session ID", width=10)
        bottom_table.add_column("Efficiency", justify="right")
        bottom_table.add_column("Grade", justify="center")
        bottom_table.add_column("Savings", justify="right")

        for sm in bottom3:
            bottom_table.add_row(
                sm.session.session_id[:8],
                f"{sm.cache_efficiency_score:.2f}",
                _grade_text(sm.grade()),
                _fmt_cost(sm.savings),
            )

        console.print(top_table)
        console.print()
        console.print(bottom_table)
        console.print()

    # 5. Tips panel
    tips: list[str] = []
    avg_hit = agg["avg_hit_rate"]
    if avg_hit < 0.40:
        tips.append(
            "• Low hit rate ({:.1f}%). Consider increasing the system prompt size "
            "or adding explicit cache_control blocks.".format(avg_hit * 100)
        )
    elif avg_hit > 0.80:
        tips.append(
            "• Excellent hit rate ({:.1f}%)! Cache is working efficiently.".format(
                avg_hit * 100
            )
        )
    else:
        tips.append(
            "• Moderate hit rate ({:.1f}%). There may be room for improvement.".format(
                avg_hit * 100
            )
        )

    has_negative_net = any(sm.net_savings < 0 for sm in sessions_metrics)
    if has_negative_net:
        tips.append(
            "• Some sessions cost more due to cache write overhead — "
            "this is normal for first requests in a session."
        )

    if agg["avg_efficiency_score"] < 0.30:
        tips.append(
            "• Low average efficiency score. Sessions with short conversations "
            "or highly variable prompts tend to benefit less from caching."
        )

    tips_text = "\n".join(tips)
    console.print(
        Panel(tips_text, title="Tips", border_style="blue", expand=False)
    )


def print_no_sessions_message() -> None:
    """Print a friendly message when no sessions are found."""
    console.print(
        Panel(
            "No JSONL session files found.\n\n"
            "Expected location: ~/.claude/projects/<project>/<session>.jsonl\n"
            "Make sure you have Claude Code sessions in the specified path.",
            title="No Sessions Found",
            border_style="yellow",
            expand=False,
        )
    )
