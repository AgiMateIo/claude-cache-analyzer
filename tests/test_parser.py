"""Tests for parser module."""

import tempfile
from pathlib import Path

from claude_cache_analyzer.parser import Session, TurnUsage, discover_sessions, parse_session_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
        f.write("")
        path = Path(f.name)
    session = parse_session_file(path)
    assert session.turns == []
    path.unlink()


def test_parse_ignores_user_events():
    session = parse_session_file(FIXTURES / "sample_session.jsonl")
    # sample has 3 assistant events, 1 user event, 1 invalid line
    assert len(session.turns) == 3
    for turn in session.turns:
        assert isinstance(turn, TurnUsage)


def test_parse_invalid_json_line_skipped():
    session = parse_session_file(FIXTURES / "sample_session.jsonl")
    # Invalid JSON line should be silently skipped, still 3 turns
    assert len(session.turns) == 3


def test_hit_rate_calculation():
    session = parse_session_file(FIXTURES / "sample_session.jsonl")
    # Turn 0: cache_creation=8500, cache_read=7200 → hit_rate = 7200/15700
    turn0 = session.turns[0]
    assert turn0.cache_creation_tokens == 8500
    assert turn0.cache_read_tokens == 7200
    expected = 7200 / (8500 + 7200)
    assert abs(turn0.hit_rate - expected) < 1e-9

    # Turn 2 (cold start): cache_creation=5000, cache_read=0 → hit_rate = 0
    turn2 = session.turns[2]
    assert turn2.hit_rate == 0.0

    # Turn 1: cache_creation=0, cache_read=15000 → hit_rate = 1.0
    turn1 = session.turns[1]
    assert turn1.hit_rate == 1.0


def test_session_properties():
    session = parse_session_file(FIXTURES / "sample_session.jsonl")
    assert session.model == "claude-sonnet-4-20250514"
    assert session.num_turns == 3
    assert session.total_input == 1200 + 500 + 3000
    assert session.total_output == 340 + 200 + 100
    assert session.total_cache_creation == 8500 + 0 + 5000
    assert session.total_cache_read == 7200 + 15000 + 0
    assert session.total_cacheable == session.total_cache_creation + session.total_cache_read

    expected_hit = session.total_cache_read / session.total_cacheable
    assert abs(session.hit_rate - expected_hit) < 1e-9


def test_discover_sessions_finds_jsonl():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        proj = root / "projects" / "test-project"
        proj.mkdir(parents=True)

        # Create a valid session file
        jsonl = proj / "abc12345-1234-1234-1234-123456789abc.jsonl"
        jsonl.write_text(
            '{"type":"assistant","timestamp":"2025-01-01T00:00:00Z",'
            '"message":{"model":"claude-sonnet-4-20250514",'
            '"usage":{"input_tokens":100,"output_tokens":50,'
            '"cache_creation_input_tokens":500,"cache_read_input_tokens":300}}}\n'
        )

        # Create an empty session file (should be excluded)
        empty = proj / "empty-session.jsonl"
        empty.write_text("")

        sessions = discover_sessions(root)
        assert len(sessions) == 1
        assert sessions[0].session_id == "abc12345-1234-1234-1234-123456789abc"
        assert sessions[0].project == "test-project"
