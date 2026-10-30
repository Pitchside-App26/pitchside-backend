"""Paper ledger: account state in state.json, every decision appended to decisions.jsonl."""
import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path(os.environ.get("PAPER_DATA_DIR", Path(__file__).parent / "data"))
STATE = DATA_DIR / "state.json"
DECISIONS = DATA_DIR / "decisions.jsonl"
EQUITY = DATA_DIR / "equity.jsonl"
LOCK = DATA_DIR / ".lock"

START_CASH = 100.0


def _fresh_state():
    return {"start_equity": START_CASH, "cash": START_CASH, "position": None,
            "fees_paid": 0.0, "created": time.time()}


@contextmanager
def locked():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return _fresh_state()


def save_state(state):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)


def _append(path, record):
    with open(path, "a") as fh:
        fh.write(json.dumps(record) + "\n")


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def log_decision(action, status, reason, symbol=None, price=None, size=None,
                 usd=None, fee=0.0, refusal=None, round_id=None):
    record = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ts": time.time(),
        "round": round_id,
        "action": action,          # buy | sell_all | hold
        "status": status,          # filled | refused | logged
        "symbol": symbol,
        "price": price,
        "size": size,              # coin quantity
        "usd": usd,
        "fee": round(fee, 6),
        "reason": " ".join(str(reason).split())[:240],
        "refusal": refusal,
    }
    _append(DECISIONS, record)
    return record


def log_equity(equity, cash, position_value, note=""):
    _append(EQUITY, {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "ts": time.time(), "equity": round(equity, 6), "cash": round(cash, 6),
                     "position_value": round(position_value, 6), "note": note})
