#!/usr/bin/env bash
# One paper-trading round: Claude Code decides using only the paper MCP tools.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p data/logs

export PAPER_ROUND_ID="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="data/logs/round-$PAPER_ROUND_ID.log"

{
  echo "=== round $PAPER_ROUND_ID ==="
  claude -p "$(cat prompt.md)" \
    --mcp-config .mcp.json --strict-mcp-config \
    --tools "" \
    --allowedTools "mcp__paper__get_account,mcp__paper__get_candles,mcp__paper__buy,mcp__paper__sell_all,mcp__paper__hold" \
    --permission-mode dontAsk \
    || echo "claude exited with status $?"
  .venv/bin/python snapshot.py
  .venv/bin/python dashboard.py
} 2>&1 | tee "$LOG"
