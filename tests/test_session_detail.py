"""Tests for session detail feature (find_session_by_id + print_session_detail)."""

from io import StringIO
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from claude_cache_analyzer.parser import Session, TurnUsage, find_session_by_id
from claude_cache_analyzer.metrics import compute_session_metrics
from claude_cache_analyzer import report as report_module


def _make_session(session_id: str, project: str = "test-proj") -> Session:
    """Helper to create a minimal session with one turn."""
    return Session(
        session_id=session_id,
        project=project,
        path=Path(f"/tmp/{session_id}.jsonl"),
        turns=[
            TurnUsage(
                timestamp=datetime(2025, 3, 13, 10, 0, 0, tzinfo=timezone.utc),
                model="claude-sonnet-4-20250514",
                input_tokens=1000,
                output_tokens=200,
                cache_creation_tokens=5000,
                cache_read_tokens=3000,
            ),
        ],
    )


def _sessions_list() -> list[Session]:
    return [
        _make_session("aaaa1111-1111-1111-1111-111111111111"),
        _make_session("aaaa2222-2222-2222-2222-222222222222"),
        _make_session("bbbb3333-3333-3333-3333-333333333333"),
    ]


def test_find_session_exact_match():
    sessions = _sessions_list()
    match, candidates = find_session_by_id(sessions, "bbbb3333-3333-3333-3333-333333333333")
    assert match is not None
    assert match.session_id == "bbbb3333-3333-3333-3333-333333333333"
    assert candidates == [match]


def test_find_session_prefix_match():
    sessions = _sessions_list()
    match, candidates = find_session_by_id(sessions, "bbbb3333")
    assert match is not None
    assert match.session_id == "bbbb3333-3333-3333-3333-333333333333"
    assert len(candidates) == 1


def test_find_session_ambiguous():
    sessions = _sessions_list()
    match, candidates = find_session_by_id(sessions, "aaaa")
    assert match is None
    assert len(candidates) == 2
    ids = {c.session_id for c in candidates}
    assert "aaaa1111-1111-1111-1111-111111111111" in ids
    assert "aaaa2222-2222-2222-2222-222222222222" in ids


def test_find_session_not_found():
    sessions = _sessions_list()
    match, candidates = find_session_by_id(sessions, "zzzz")
    assert match is None
    assert candidates == []


def test_session_detail_renders():
    """Verify print_session_detail produces output without errors."""
    sess = Session(
        session_id="abcd1234-5678-9012-3456-789012345678",
        project="test-project",
        path=Path("/tmp/test.jsonl"),
        turns=[
            TurnUsage(
                timestamp=datetime(2025, 3, 13, 10, 0, 0, tzinfo=timezone.utc),
                model="claude-sonnet-4-20250514",
                input_tokens=1200,
                output_tokens=340,
                cache_creation_tokens=8500,
                cache_read_tokens=0,
            ),
            TurnUsage(
                timestamp=datetime(2025, 3, 13, 10, 5, 0, tzinfo=timezone.utc),
                model="claude-sonnet-4-20250514",
                input_tokens=500,
                output_tokens=200,
                cache_creation_tokens=0,
                cache_read_tokens=15000,
            ),
            TurnUsage(
                timestamp=datetime(2025, 3, 13, 10, 10, 0, tzinfo=timezone.utc),
                model="claude-sonnet-4-20250514",
                input_tokens=3000,
                output_tokens=100,
                cache_creation_tokens=5000,
                cache_read_tokens=4000,
            ),
        ],
    )
    sm = compute_session_metrics(sess)

    # Capture output by temporarily replacing the module's console
    buf = StringIO()
    test_console = Console(file=buf, width=160, force_terminal=True)
    original_console = report_module.console
    report_module.console = test_console
    try:
        report_module.print_session_detail(sm)
    finally:
        report_module.console = original_console

    output = buf.getvalue()

    # Verify key sections are present
    assert "Session Detail" in output
    assert "abcd1234" in output
    assert "Session Summary" in output
    assert "Per-Turn Breakdown" in output
    assert "Token Composition" in output
    assert "Tips" in output
    # Cold start detected on turn 1
    assert "Cold start" in output
    assert "#1" in output
