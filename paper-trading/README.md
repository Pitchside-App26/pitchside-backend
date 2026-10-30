# Paper-trading experiment

**Paper money only. Not financial advice.** No broker, exchange, wallet or API key is used anywhere. The only network call goes to Kraken's free public market-data endpoints (`/0/public/OHLC` and `/0/public/Ticker`).

## Files

| File | What it does |
|---|---|
| `market.py` | Hourly (also 4h/1d) candles for BTC, ETH and SOL from Kraken. Drops the newest candle because it is still forming. The latest price comes from the public ticker. |
| `server.py` | MCP server (`mcp` 2.x, `MCPServer`). Read tools: `get_candles`, `get_account`. Write tools: `buy`, `sell_all`, `hold`. |
| `gate.py` | Risk gate that every write goes through first. |
| `ledger.py` | $100 paper account (`data/state.json`), a log of every decision (`data/decisions.jsonl`) and equity snapshots (`data/equity.jsonl`). |
| `prompt.md` | The trading prompt for each round. **Edit this file to change the strategy.** |
| `run_round.sh` | Runs one round: Claude Code with only the five paper tools, then an equity snapshot, then the dashboard. |
| `dashboard.py` | Writes `dashboard.html`. |
| `test_paper.py` | Offline tests for the gate and ledger, using stub prices in a temporary folder. |

## Risk rules (`gate.py`)

- One position at a time. Selling with no position is refused, so there is no shorting.
- A single entry can use at most 25% of current equity, and no more than the cash available (no leverage).
- 0.4% fee on every fill. On a buy, `usd_amount` includes the fee.
- At most 6 fills per UTC day. This limit also applies to `sell_all`, so in principle it could block an exit. Running every 4 hours gives at most 6 rounds a day, so the limit can't be reached at that schedule.
- No new buys once equity is below $50 (50% of the start). `sell_all` is still allowed.
- Extra rule: at most one filled order per round, so a single round can't buy, sell and buy again and pay fees each time.

Every call is logged with time, symbol, price, size, fee and a one-line reason. That includes holds and refused orders, along with the gate's refusal message.

## Setup (macOS / Linux)

```bash
cd paper-trading
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest test_paper     # optional sanity check
```

The MCP server is registered with Claude Code at project scope through `.mcp.json`. Run `claude` once inside `paper-trading/` and approve the `paper` server if you also want to use it interactively. `run_round.sh` loads the server with `--mcp-config`, so scheduled runs don't need that approval.

## Run one round

```bash
./run_round.sh
open dashboard.html        # Linux: xdg-open dashboard.html
```

## Run every 4 hours

Your computer has to be awake for a round to run. Rounds missed while it is asleep are skipped, which is fine for this experiment.

**macOS / Linux (cron):** run `crontab -e` and add this line, using your own absolute path:

```
7 */4 * * * /ABSOLUTE/PATH/paper-trading/run_round.sh >/dev/null 2>&1
```

Cron runs with a minimal `PATH`, so `claude` may not be found. Run `which claude` and add its folder at the top of the crontab, for example `PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin`. Each round writes its own log to `data/logs/`.

**Windows:** use WSL and the cron line above, or Task Scheduler running `wsl /ABSOLUTE/PATH/paper-trading/run_round.sh` every 4 hours.

## Reset

Delete `data/` to start again from $100.

## Real money

This is a paper experiment. The decision log and equity history are what you would study before ever considering a real trading model. They are not a reason to connect this to an account.
