# Claude Code Cache Efficiency Analyzer

Based on https://habr.com/ru/companies/bitrix/articles/1008320/

It helps to analyze you Claude Agent SDK usage.

CLI tool that reads Claude Code JSONL session files, computes prompt cache efficiency metrics using the Bitrix24/Habr formula, and displays results as rich terminal tables.

## Formula

```
C = S × [(1−h) × P_miss + h × P_hit] + D × P_miss + O × P_out
```

Where: **S** = cacheable tokens, **h** = hit rate, **D** = dynamic input tokens, **O** = output tokens.

## Install & Run

### Via uvx (no install needed)

```bash
uvx claude-cache-analyzer
```

### Via pip

```bash
pip install claude-cache-analyzer
claude-cache
```

### From source

```bash
git clone https://github.com/AgiMateIo/claude-cache-analyzer.git
cd claude-cache-analyzer
uv sync
uv run python cli.py
```

## Usage

```
Usage: claude-cache-analyzer [OPTIONS] [PROJECT_PATH]

 Analyze Claude Code prompt cache efficiency.

Arguments:
  [PROJECT_PATH]  Root of Claude data (~/.claude) or a specific project directory.

Options:
  -p, --project-name     TEXT     Filter by project directory name.
  -n, --top              INTEGER  Show only the N most recent sessions.
      --min-turns        INTEGER  Minimum number of turns to include a session. [default: 1]
  -s, --session          TEXT     Show detailed view for a specific session (full or partial ID).
  -g, --group-by-project          Group results by project.
      --export-json      PATH     Export raw metrics to a JSON file.
      --version                   Show version.
  -h, --help                      Show this message and exit.
```

### Examples

```bash
# Analyze all sessions in ~/.claude
claude-cache-analyzer

# Last 5 sessions
claude-cache-analyzer --top 5

# Specific project
claude-cache-analyzer --project-name my-project

# Detailed view of a specific session (full or partial ID)
claude-cache-analyzer -s abcd1234

# Group by project
claude-cache-analyzer -g

# Export metrics to JSON
claude-cache-analyzer --export-json metrics.json

# Analyze a specific path
claude-cache-analyzer ~/.claude/projects/abc123
```

## Metrics

| Metric | Description |
|--------|-------------|
| Cache hit rate | `cache_read / (cache_creation + cache_read)` |
| Actual cost | Real cost with cache pricing applied |
| Cost without cache | Hypothetical cost if all tokens were at input price |
| Savings | `cost_no_cache - actual_cost` |
| Net savings | Savings minus cache write overhead |
| Efficiency score | `hit_rate × (cacheable / (input + cacheable))` — range [0..1] |

## Grades

| Grade | Efficiency Score |
|-------|-----------------|
| **A** | ≥ 0.70 |
| **B** | ≥ 0.50 |
| **C** | ≥ 0.30 |
| **D** | ≥ 0.10 |
| **F** | < 0.10 |

## Tests

```bash
uv run pytest -v
```
