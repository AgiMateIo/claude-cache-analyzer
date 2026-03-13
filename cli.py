"""Thin wrapper — delegates to claude_cache_analyzer.cli for backwards compat."""

from claude_cache_analyzer.cli import app

if __name__ == "__main__":
    app()
