# Claude Code Cache Efficiency Analyzer

Based on https://habr.com/ru/companies/bitrix/articles/1008320/

It helps to analyze you Claude Agent SDK usage.

CLI tool that reads Claude Code JSONL session files, computes prompt cache efficiency metrics using the Bitrix24/Habr formula, and displays results as rich terminal tables.

## Formula

```
C = S × [(1−h) × P_miss + h × P_hit] + D × P_miss + O × P_out
```

Where: **S** = cacheable tokens, **h** = hit rate, **D** = dynamic input tokens, **O** = output tokens.

## Install

```bash
uv sync
```

## Usage

```bash
# Analyze all sessions in ~/.claude
uv run python cli.py

# Last 5 sessions
uv run python cli.py --top 5

# Specific project
uv run python cli.py --project-name my-project

# Export metrics to JSON
uv run python cli.py --export-json metrics.json

# Analyze a specific path
uv run python cli.py ~/.claude/projects/abc123
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
