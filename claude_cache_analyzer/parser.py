"""Parse Claude Code JSONL session files into structured data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rich.console import Console

console = Console(stderr=True)


@dataclass
class TurnUsage:
    timestamp: datetime | None
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens

    @property
    def cacheable_tokens(self) -> int:
        return self.cache_creation_tokens + self.cache_read_tokens

    @property
    def hit_rate(self) -> float:
        if self.cacheable_tokens == 0:
            return 0.0
        return self.cache_read_tokens / self.cacheable_tokens


@dataclass
class Session:
    session_id: str
    project: str
    path: Path
    turns: list[TurnUsage] = field(default_factory=list)

    @property
    def model(self) -> str:
        if not self.turns:
            return "unknown"
        return self.turns[-1].model

    @property
    def started_at(self) -> datetime | None:
        timestamps = [t.timestamp for t in self.turns if t.timestamp is not None]
        if not timestamps:
            return None
        return min(timestamps)

    @property
    def total_input(self) -> int:
        return sum(t.input_tokens for t in self.turns)

    @property
    def total_output(self) -> int:
        return sum(t.output_tokens for t in self.turns)

    @property
    def total_cache_creation(self) -> int:
        return sum(t.cache_creation_tokens for t in self.turns)

    @property
    def total_cache_read(self) -> int:
        return sum(t.cache_read_tokens for t in self.turns)

    @property
    def total_cacheable(self) -> int:
        return self.total_cache_creation + self.total_cache_read

    @property
    def hit_rate(self) -> float:
        if self.total_cacheable == 0:
            return 0.0
        return self.total_cache_read / self.total_cacheable

    @property
    def num_turns(self) -> int:
        return len(self.turns)


def parse_session_file(path: Path) -> Session:
    """Read a JSONL session file and extract TurnUsage from assistant events."""
    session_id = path.stem
    project = path.parent.name

    turns: list[TurnUsage] = []

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("type") != "assistant":
                    continue

                message = event.get("message")
                if not message or not isinstance(message, dict):
                    continue

                usage = message.get("usage")
                if not usage or not isinstance(usage, dict):
                    continue

                timestamp = None
                ts_str = event.get("timestamp")
                if ts_str:
                    try:
                        timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                model = message.get("model", "unknown")

                turns.append(
                    TurnUsage(
                        timestamp=timestamp,
                        model=model,
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                        cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                    )
                )
    except OSError as e:
        console.log(f"[red]Error reading {path}: {e}[/red]")

    return Session(session_id=session_id, project=project, path=path, turns=turns)


def find_session_by_id(
    sessions: list[Session], session_id: str
) -> tuple[Session | None, list[Session]]:
    """Find a session by exact or prefix match on session_id.

    Returns (match, candidates):
      - (session, [session]) if exactly one match
      - (None, [s1, s2, ...]) if ambiguous (multiple prefix matches)
      - (None, []) if not found
    """
    # Exact match first
    for s in sessions:
        if s.session_id == session_id:
            return s, [s]

    # Prefix match
    candidates = [s for s in sessions if s.session_id.startswith(session_id)]
    if len(candidates) == 1:
        return candidates[0], candidates
    if len(candidates) > 1:
        return None, candidates
    return None, []


def discover_sessions(claude_root: Path) -> list[Session]:
    """Recursively find JSONL sessions under claude_root/projects/."""
    projects_dir = claude_root / "projects"
    if not projects_dir.exists():
        return []

    sessions: list[Session] = []
    for jsonl_path in projects_dir.rglob("*.jsonl"):
        session = parse_session_file(jsonl_path)
        if session.turns:
            sessions.append(session)

    sessions.sort(key=lambda s: s.started_at or datetime.min, reverse=True)
    return sessions
