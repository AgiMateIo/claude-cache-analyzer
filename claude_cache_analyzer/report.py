"""Rich terminal output for cache efficiency reports."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from datetime import timedelta

from .metrics import AggregateMetrics, SessionMetrics, aggregate

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


def _truncate_left(s: str, max_width: int) -> str:
    """Truncate string from the left with '…' prefix if too long."""
    if len(s) <= max_width:
        return s
    return "…" + s[-(max_width - 1):]


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

    summary.add_row("Total actual cost", _fmt_cost(agg.total_actual_cost))
    summary.add_row("Cost without cache", _fmt_cost(agg.total_cost_no_cache))
    summary.add_row("Total savings", _fmt_cost(agg.total_savings))
    summary.add_row(
        "Net savings (after write overhead)", _fmt_cost(agg.total_net_savings)
    )
    if agg.total_cost_no_cache > 0:
        savings_pct = agg.total_savings / agg.total_cost_no_cache * 100
    else:
        savings_pct = 0.0
    summary.add_row("Savings %", _fmt_pct(savings_pct))
    summary.add_row("Avg cache hit rate", _fmt_pct(agg.avg_hit_rate * 100))
    summary.add_row("Avg efficiency score", f"{agg.avg_efficiency_score:.2f}")

    console.print(summary)
    console.print()

    # 3. Sessions table
    sessions_table = Table(
        title="Sessions", show_header=True, header_style="bold cyan"
    )
    sessions_table.add_column("#", justify="right", style="dim", width=4)
    sessions_table.add_column("Session ID", width=15)
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
            sess.session_id[:13],
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

        half = len(sorted_by_eff) // 2
        top3 = sorted_by_eff[:min(3, half)]
        bottom3 = sorted_by_eff[-min(3, len(sorted_by_eff) - half):]

        # Estimate space for project column in small tables:
        # Session(15) + Efficiency(10) + Grade(6) + Savings(10) + borders ≈ 60
        _small_max_proj = max(console.width - 60, 16)

        top_table = Table(title="🏆 Top 3", show_header=True, header_style="bold green")
        top_table.add_column("Session ID", width=15)
        top_table.add_column("Project", no_wrap=True)
        top_table.add_column("Efficiency", justify="right")
        top_table.add_column("Grade", justify="center")
        top_table.add_column("Savings", justify="right")

        for sm in top3:
            top_table.add_row(
                sm.session.session_id[:13],
                _truncate_left(sm.session.project, _small_max_proj),
                f"{sm.cache_efficiency_score:.2f}",
                _grade_text(sm.grade()),
                _fmt_cost(sm.savings),
            )

        bottom_table = Table(
            title="⚠️  Bottom 3", show_header=True, header_style="bold red"
        )
        bottom_table.add_column("Session ID", width=15)
        bottom_table.add_column("Project", no_wrap=True)
        bottom_table.add_column("Efficiency", justify="right")
        bottom_table.add_column("Grade", justify="center")
        bottom_table.add_column("Savings", justify="right")

        for sm in bottom3:
            bottom_table.add_row(
                sm.session.session_id[:13],
                _truncate_left(sm.session.project, _small_max_proj),
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
    avg_hit = agg.avg_hit_rate
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

    if agg.avg_efficiency_score < 0.30:
        tips.append(
            "• Low average efficiency score. Sessions with short conversations "
            "or highly variable prompts tend to benefit less from caching."
        )

    tips_text = "\n".join(tips)
    console.print(
        Panel(tips_text, title="Tips", border_style="blue", expand=False)
    )


def print_session_detail(sm: SessionMetrics) -> None:
    """Print a detailed turn-by-turn report for a single session."""
    sess = sm.session
    started = sess.started_at
    ended_ts = [t.timestamp for t in sess.turns if t.timestamp is not None]
    ended = max(ended_ts) if ended_ts else None

    # 1. Header panel
    date_str = started.strftime("%Y-%m-%d %H:%M") if started else "—"
    if started and ended and ended > started:
        duration = ended - started
        total_secs = int(duration.total_seconds())
        h, rem = divmod(total_secs, 3600)
        m, s = divmod(rem, 60)
        dur_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"
    else:
        dur_str = "—"

    grade = sm.grade()
    header = Text.assemble(
        ("   Claude Code · Session Detail\n", "bold white"),
        (f"   Session: {sess.session_id}\n", "dim"),
        (f"   File: {sess.path}\n", "dim"),
        (f"   Project: {sess.project}  ·  Model: {sess.model}\n", "dim"),
        (f"   Date: {date_str}  ·  Duration: {dur_str}  ·  ", "dim"),
        (f"Turns: {sess.num_turns}  ·  Grade: ", "dim"),
        (grade, f"bold {GRADE_COLORS.get(grade, 'white')}"),
    )
    console.print(Panel(header, style="bold blue", expand=False))
    console.print()

    # 2. Session summary table
    summary = Table(title="Session Summary", show_header=True, header_style="bold magenta")
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")

    summary.add_row("Actual cost", _fmt_cost(sm.actual_cost))
    summary.add_row("Cost without cache", _fmt_cost(sm.cost_no_cache))
    summary.add_row("Savings", _fmt_cost(sm.savings))
    summary.add_row("Net savings (after write overhead)", _fmt_cost(sm.net_savings))
    summary.add_row("Savings %", _fmt_pct(sm.savings_pct))
    summary.add_row("Cache hit rate", _hit_rate_bar(sm.hit_rate))
    summary.add_row("Efficiency score", f"{sm.cache_efficiency_score:.2f}")
    summary.add_row("Total input tokens", _fmt_tokens(sess.total_input + sess.total_cacheable))
    summary.add_row("Total output tokens", _fmt_tokens(sess.total_output))

    console.print(summary)
    console.print()

    # 3. Per-turn table
    turns_table = Table(title="Per-Turn Breakdown", show_header=True, header_style="bold cyan")
    turns_table.add_column("#", justify="right", style="dim", width=4)
    turns_table.add_column("Time", width=8)
    turns_table.add_column("Input", justify="right", width=10)
    turns_table.add_column("Cache Write", justify="right", width=12)
    turns_table.add_column("Cache Read", justify="right", width=12)
    turns_table.add_column("Output", justify="right", width=10)
    turns_table.add_column("Hit%", width=22)
    turns_table.add_column("Actual $", justify="right", width=10)
    turns_table.add_column("No-Cache $", justify="right", width=10)
    turns_table.add_column("Savings $", justify="right", width=10)
    turns_table.add_column("Cum. Cost $", justify="right", width=11)

    cumulative_cost = 0.0
    for i, tm in enumerate(sm.turns, 1):
        turn = tm.turn
        cumulative_cost += tm.actual_cost

        # Time offset from session start
        if started and turn.timestamp:
            delta = turn.timestamp - started
            total_secs = int(delta.total_seconds())
            m, s = divmod(total_secs, 60)
            time_str = f"+{m}m{s:02d}s"
        else:
            time_str = "—"

        turns_table.add_row(
            str(i),
            time_str,
            _fmt_tokens(turn.input_tokens),
            _fmt_tokens(turn.cache_creation_tokens),
            _fmt_tokens(turn.cache_read_tokens),
            _fmt_tokens(turn.output_tokens),
            _hit_rate_bar(turn.hit_rate, width=12),
            _fmt_cost(tm.actual_cost),
            _fmt_cost(tm.cost_no_cache),
            _fmt_cost(tm.savings),
            _fmt_cost(cumulative_cost),
        )

    console.print(turns_table)
    console.print()

    # 4. Token composition table
    total_tokens = sess.total_input + sess.total_cacheable
    comp_table = Table(title="Token Composition", show_header=True, header_style="bold magenta")
    comp_table.add_column("Category", style="bold")
    comp_table.add_column("Tokens", justify="right")
    comp_table.add_column("% of Input", justify="right")

    def _pct_of(val: int) -> str:
        return _fmt_pct(val / total_tokens * 100) if total_tokens > 0 else "0.0%"

    comp_table.add_row("Cache Read", _fmt_tokens(sess.total_cache_read), _pct_of(sess.total_cache_read))
    comp_table.add_row("Cache Write", _fmt_tokens(sess.total_cache_creation), _pct_of(sess.total_cache_creation))
    comp_table.add_row("Dynamic Input", _fmt_tokens(sess.total_input), _pct_of(sess.total_input))
    comp_table.add_row("Total Input", _fmt_tokens(total_tokens), "100.0%")
    comp_table.add_row("Output", _fmt_tokens(sess.total_output), "—")

    console.print(comp_table)
    console.print()

    # 5. Session-specific tips
    tips: list[str] = []

    # Cold start detection
    cold_starts = [
        i + 1
        for i, tm in enumerate(sm.turns)
        if tm.turn.cache_creation_tokens > 0 and tm.turn.cache_read_tokens == 0
    ]
    if cold_starts:
        turns_str = ", ".join(f"#{n}" for n in cold_starts)
        tips.append(f"• Cold start turns (cache write only, no reads): {turns_str}")

    # Mid-session cache re-creation
    mid_recreations = [
        i + 1
        for i, tm in enumerate(sm.turns)
        if i > 0 and tm.turn.cache_creation_tokens > 0 and tm.turn.cache_read_tokens > 0
    ]
    if mid_recreations:
        turns_str = ", ".join(f"#{n}" for n in mid_recreations)
        tips.append(
            f"• Mid-session cache re-creation at turns {turns_str} — "
            "prompt prefix may have changed, triggering partial cache invalidation."
        )

    # Hit rate advice
    hit = sm.hit_rate
    if hit < 0.40:
        tips.append(
            f"• Low hit rate ({hit*100:.1f}%). Consider keeping the prompt prefix stable "
            "or adding explicit cache_control breakpoints."
        )
    elif hit > 0.80:
        tips.append(f"• Excellent hit rate ({hit*100:.1f}%)! Cache is working efficiently.")
    else:
        tips.append(f"• Moderate hit rate ({hit*100:.1f}%). There may be room for improvement.")

    if sm.net_savings < 0:
        tips.append(
            "• Net savings are negative — cache write overhead exceeded read savings. "
            "This is typical for short sessions with few turns."
        )

    tips_text = "\n".join(tips) if tips else "No specific recommendations."
    console.print(Panel(tips_text, title="Tips", border_style="blue", expand=False))


def print_grouped_report(
    sessions_metrics: list[SessionMetrics],
) -> None:
    """Print a report grouped by project."""
    from itertools import groupby

    # Group by project
    sorted_sm = sorted(sessions_metrics, key=lambda sm: sm.session.project)
    groups: list[tuple[str, list[SessionMetrics]]] = [
        (proj, list(items))
        for proj, items in groupby(sorted_sm, key=lambda sm: sm.session.project)
    ]

    # Sort groups by total actual cost descending
    groups.sort(key=lambda g: sum(sm.actual_cost for sm in g[1]), reverse=True)

    total_sessions = len(sessions_metrics)

    # Header
    header = Text.assemble(
        ("   Claude Code · Cache Efficiency Report\n", "bold white"),
        (
            f"   {len(groups)} projects  ·  {total_sessions} sessions analysed",
            "dim",
        ),
    )
    console.print(Panel(header, style="bold blue", expand=False))
    console.print()

    # Overall summary
    agg = aggregate(sessions_metrics)
    summary = Table(title="Overall Summary", show_header=True, header_style="bold magenta")
    summary.add_column("Metric", style="bold")
    summary.add_column("Value", justify="right")
    summary.add_row("Total actual cost", _fmt_cost(agg.total_actual_cost))
    summary.add_row("Cost without cache", _fmt_cost(agg.total_cost_no_cache))
    summary.add_row("Total savings", _fmt_cost(agg.total_savings))
    summary.add_row("Net savings (after write overhead)", _fmt_cost(agg.total_net_savings))
    if agg.total_cost_no_cache > 0:
        savings_pct = agg.total_savings / agg.total_cost_no_cache * 100
    else:
        savings_pct = 0.0
    summary.add_row("Savings %", _fmt_pct(savings_pct))
    summary.add_row("Avg cache hit rate", _fmt_pct(agg.avg_hit_rate * 100))
    summary.add_row("Avg efficiency score", f"{agg.avg_efficiency_score:.2f}")
    console.print(summary)
    console.print()

    # Per-project table
    proj_table = Table(
        title="By Project", show_header=True, header_style="bold cyan"
    )
    proj_table.add_column("#", justify="right", style="dim", width=4)
    proj_table.add_column("Project", no_wrap=True)
    proj_table.add_column("Sessions", justify="right", width=9)
    proj_table.add_column("Turns", justify="right", width=7)
    proj_table.add_column("Cache hit%", width=28)
    proj_table.add_column("Efficiency", justify="right", width=10)
    proj_table.add_column("Grade", justify="center", width=6)
    proj_table.add_column("Actual $", justify="right", width=10)
    proj_table.add_column("Savings $", justify="right", width=10)
    proj_table.add_column("Savings %", justify="right", width=10)

    # Estimate space for project column: total width minus fixed columns and borders
    # 9 fixed columns = 94 chars + 11 borders + 20 padding (2 per col) = 125
    max_proj_width = max(console.width - 125, 16)

    for i, (proj_name, proj_metrics) in enumerate(groups, 1):
        proj_agg = aggregate(proj_metrics)
        total_turns = sum(sm.session.num_turns for sm in proj_metrics)
        avg_eff = proj_agg.avg_efficiency_score

        if avg_eff >= 0.70:
            grade = "A"
        elif avg_eff >= 0.50:
            grade = "B"
        elif avg_eff >= 0.30:
            grade = "C"
        elif avg_eff >= 0.10:
            grade = "D"
        else:
            grade = "F"

        if proj_agg.total_cost_no_cache > 0:
            sav_pct = proj_agg.total_savings / proj_agg.total_cost_no_cache * 100
        else:
            sav_pct = 0.0

        proj_table.add_row(
            str(i),
            _truncate_left(proj_name, max_proj_width),
            str(len(proj_metrics)),
            str(total_turns),
            _hit_rate_bar(proj_agg.avg_hit_rate),
            f"{avg_eff:.2f}",
            _grade_text(grade),
            _fmt_cost(proj_agg.total_actual_cost),
            _fmt_cost(proj_agg.total_savings),
            _fmt_pct(sav_pct),
        )

    console.print(proj_table)
    console.print()


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
