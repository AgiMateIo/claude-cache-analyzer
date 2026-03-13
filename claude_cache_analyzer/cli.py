"""CLI entry point for Claude Code Cache Efficiency Analyzer."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from claude_cache_analyzer import __version__
from claude_cache_analyzer.metrics import aggregate, compute_session_metrics
from claude_cache_analyzer.parser import discover_sessions, find_session_by_id, parse_session_file
from claude_cache_analyzer.report import (
    print_grouped_report,
    print_no_sessions_message,
    print_project_report,
    print_session_detail,
)

app = typer.Typer(
    help="Analyze Claude Code session cache efficiency.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"claude-cache-analyzer {__version__}")
        raise typer.Exit()


@app.command()
def main(
    project_path: Optional[Path] = typer.Argument(
        None,
        help="Root of Claude data (~/.claude) or a specific project directory.",
    ),
    project_name: Optional[str] = typer.Option(
        None, "--project-name", "-p", help="Filter by project directory name."
    ),
    top: Optional[int] = typer.Option(
        None, "--top", "-n", help="Show only the N most recent sessions."
    ),
    min_turns: int = typer.Option(
        1, "--min-turns", help="Minimum number of turns to include a session."
    ),
    session: Optional[str] = typer.Option(
        None, "--session", "-s", help="Show detailed view for a specific session (full or partial ID)."
    ),
    group_by_project: bool = typer.Option(
        False, "--group-by-project", "-g", help="Group results by project."
    ),
    export_json: Optional[Path] = typer.Option(
        None, "--export-json", help="Export raw metrics to a JSON file."
    ),
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """Analyze Claude Code prompt cache efficiency."""
    if project_path is None:
        project_path = Path.home() / ".claude"

    project_path = project_path.expanduser().resolve()

    # Determine if path points to a specific project or the root
    if (project_path / "projects").is_dir():
        # Root claude dir
        sessions = discover_sessions(project_path)
    elif project_path.is_dir():
        # Might be a specific project directory — look for JSONL files directly
        jsonl_files = list(project_path.glob("*.jsonl"))
        if jsonl_files:
            sessions = []
            for f in jsonl_files:
                s = parse_session_file(f)
                if s.turns:
                    sessions.append(s)
            sessions.sort(
                key=lambda s: s.started_at or datetime.min, reverse=True
            )
        else:
            # Maybe it's a projects/ parent
            sessions = discover_sessions(project_path)
    else:
        console.print(f"[red]Path does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    if not sessions:
        print_no_sessions_message()
        raise typer.Exit()

    # Session detail mode
    if session:
        match, candidates = find_session_by_id(sessions, session)
        if match is None and not candidates:
            console.print(f"[red]No session found matching '{session}'[/red]")
            raise typer.Exit(1)
        if match is None:
            console.print(f"[yellow]Ambiguous session ID '{session}'. Candidates:[/yellow]")
            for c in candidates:
                date_str = c.started_at.strftime("%Y-%m-%d %H:%M") if c.started_at else "—"
                console.print(f"  {c.session_id}  ({date_str}, {c.num_turns} turns)")
            raise typer.Exit(1)

        sm = compute_session_metrics(match)
        print_session_detail(sm)

        if export_json:
            export_data = {
                "session_id": match.session_id,
                "project": match.project,
                "model": match.model,
                "started_at": match.started_at.isoformat() if match.started_at else None,
                "num_turns": match.num_turns,
                "hit_rate": sm.hit_rate,
                "efficiency_score": sm.cache_efficiency_score,
                "grade": sm.grade(),
                "actual_cost": sm.actual_cost,
                "cost_no_cache": sm.cost_no_cache,
                "savings": sm.savings,
                "net_savings": sm.net_savings,
                "savings_pct": sm.savings_pct,
                "turns": [
                    {
                        "timestamp": tm.turn.timestamp.isoformat() if tm.turn.timestamp else None,
                        "model": tm.turn.model,
                        "input_tokens": tm.turn.input_tokens,
                        "output_tokens": tm.turn.output_tokens,
                        "cache_creation_tokens": tm.turn.cache_creation_tokens,
                        "cache_read_tokens": tm.turn.cache_read_tokens,
                        "hit_rate": tm.turn.hit_rate,
                        "actual_cost": tm.actual_cost,
                        "cost_no_cache": tm.cost_no_cache,
                        "savings": tm.savings,
                        "savings_pct": tm.savings_pct,
                    }
                    for tm in sm.turns
                ],
            }
            export_json.write_text(json.dumps(export_data, indent=2))
            console.print(f"\n[green]Metrics exported to {export_json}[/green]")
        raise typer.Exit()

    # Filter by project name
    if project_name:
        sessions = [s for s in sessions if project_name in s.project]

    # Filter by min turns
    sessions = [s for s in sessions if s.num_turns >= min_turns]

    if not sessions:
        print_no_sessions_message()
        raise typer.Exit()

    # Limit to top N
    if top is not None:
        sessions = sessions[:top]

    # Compute metrics
    sessions_metrics = [compute_session_metrics(s) for s in sessions]

    # Print report
    if group_by_project:
        print_grouped_report(sessions_metrics)
    else:
        display_name = project_name or (
            sessions[0].project
            if len(set(s.project for s in sessions)) == 1
            else "all projects"
        )
        print_project_report(sessions_metrics, display_name)

    # Export JSON
    if export_json:
        agg = aggregate(sessions_metrics)
        export_data = {
            "aggregate": {
                k: v
                for k, v in agg.items()
                if k not in ("best_session", "worst_session")
            },
            "sessions": [],
        }
        for sm in sessions_metrics:
            sess = sm.session
            export_data["sessions"].append(
                {
                    "session_id": sess.session_id,
                    "project": sess.project,
                    "model": sess.model,
                    "started_at": (
                        sess.started_at.isoformat() if sess.started_at else None
                    ),
                    "num_turns": sess.num_turns,
                    "total_input": sess.total_input,
                    "total_output": sess.total_output,
                    "total_cacheable": sess.total_cacheable,
                    "hit_rate": sm.hit_rate,
                    "efficiency_score": sm.cache_efficiency_score,
                    "grade": sm.grade(),
                    "actual_cost": sm.actual_cost,
                    "cost_no_cache": sm.cost_no_cache,
                    "savings": sm.savings,
                    "net_savings": sm.net_savings,
                    "savings_pct": sm.savings_pct,
                }
            )
        export_json.write_text(json.dumps(export_data, indent=2))
        console.print(f"\n[green]Metrics exported to {export_json}[/green]")


if __name__ == "__main__":
    app()
