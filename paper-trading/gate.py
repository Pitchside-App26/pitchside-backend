"""Risk gate. Every write goes through check_buy / check_sell before the ledger changes.

Returns None when allowed, or a short refusal string.
"""
import time

MAX_ENTRY_FRACTION = 0.25
FEE_RATE = 0.004
MAX_FILLS_PER_DAY = 6
KILL_SWITCH_FRACTION = 0.50


def fills_today(decisions, now=None):
    day = time.strftime("%Y-%m-%d", time.gmtime(now or time.time()))
    return sum(1 for d in decisions if d["status"] == "filled" and d["time"].startswith(day))


def writes_this_round(decisions, round_id):
    if not round_id:
        return 0
    return sum(1 for d in decisions if d.get("round") == round_id and d["action"] != "hold"
               and d["status"] == "filled")


def check_buy(state, decisions, equity, usd_amount, round_id=None):
    if not isinstance(usd_amount, (int, float)) or usd_amount != usd_amount or usd_amount <= 0:
        return "usd_amount must be a positive number"
    if state["position"] is not None:
        return f"one position at a time: already holding {state['position']['symbol']}"
    if equity < KILL_SWITCH_FRACTION * state["start_equity"]:
        return (f"kill switch: equity ${equity:.2f} is below "
                f"{KILL_SWITCH_FRACTION:.0%} of start ${state['start_equity']:.2f}; no new buys")
    cap = MAX_ENTRY_FRACTION * equity
    if usd_amount > cap + 1e-9:
        return f"entry ${usd_amount:.2f} exceeds {MAX_ENTRY_FRACTION:.0%} of equity (max ${cap:.2f})"
    if usd_amount > state["cash"] + 1e-9:
        return f"no leverage: entry ${usd_amount:.2f} exceeds cash ${state['cash']:.2f}"
    if fills_today(decisions) >= MAX_FILLS_PER_DAY:
        return f"daily fill limit reached ({MAX_FILLS_PER_DAY} fills today, UTC)"
    if writes_this_round(decisions, round_id) >= 1:
        return "one filled order per round already used"
    return None


def check_sell(state, decisions, round_id=None):
    if state["position"] is None:
        return "no shorting: there is no open position to sell"
    if fills_today(decisions) >= MAX_FILLS_PER_DAY:
        return f"daily fill limit reached ({MAX_FILLS_PER_DAY} fills today, UTC)"
    if writes_this_round(decisions, round_id) >= 1:
        return "one filled order per round already used"
    return None
