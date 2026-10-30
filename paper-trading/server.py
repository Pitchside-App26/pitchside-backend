"""Paper-trading MCP server. Paper money only: no broker, exchange, wallet or API keys."""
import os

from mcp.server import MCPServer

import gate
import ledger
import market

server = MCPServer(
    name="paper",
    instructions="Paper-trading sandbox with $100 of fake money. Every write tool passes a risk gate "
                 "and every call is logged. Nothing here touches a real account.",
)


def _round():
    return os.environ.get("PAPER_ROUND_ID")


def _equity(state):
    """Mark to market. Returns (equity, position_value, price_or_None)."""
    pos = state["position"]
    if pos is None:
        return state["cash"], 0.0, None
    price = market.latest_price(pos["symbol"])
    value = pos["qty"] * price
    return state["cash"] + value, value, price


@server.tool()
def get_candles(symbol: str, timeframe: str = "1h", limit: int = 48) -> dict:
    """Closed OHLC candles (oldest first) for BTC, ETH or SOL. timeframe: 1h, 4h or 1d. The still-forming candle is dropped."""
    try:
        return {"symbol": symbol.upper(), "timeframe": timeframe,
                "candles": market.get_candles(symbol, timeframe, limit)}
    except market.MarketDataError as e:
        return {"error": str(e)}


@server.tool()
def get_account() -> dict:
    """Cash, open position, equity, fees paid, fills used today and the risk rules."""
    with ledger.locked():
        state = ledger.load_state()
        decisions = ledger.read_jsonl(ledger.DECISIONS)
    out = {"cash": round(state["cash"], 4), "position": state["position"],
           "start_equity": state["start_equity"], "fees_paid": round(state["fees_paid"], 4),
           "fills_today": gate.fills_today(decisions),
           "rules": {"max_entry_fraction_of_equity": gate.MAX_ENTRY_FRACTION,
                     "fee_rate_per_fill": gate.FEE_RATE,
                     "max_fills_per_day": gate.MAX_FILLS_PER_DAY,
                     "no_new_buys_below_equity": gate.KILL_SWITCH_FRACTION * state["start_equity"],
                     "positions_at_once": 1, "leverage": False, "shorting": False}}
    try:
        equity, value, price = _equity(state)
        out.update(equity=round(equity, 4), position_value=round(value, 4), mark_price=price)
    except market.MarketDataError as e:
        out["equity_error"] = str(e)
    return out


@server.tool()
def buy(symbol: str, usd_amount: float, reason: str) -> dict:
    """Open a long position spending usd_amount of cash (fee included) at the latest price. Must pass the risk gate."""
    symbol = symbol.upper()
    with ledger.locked():
        state = ledger.load_state()
        decisions = ledger.read_jsonl(ledger.DECISIONS)
        try:
            price = market.latest_price(symbol)
            equity, _, _ = _equity(state)
        except market.MarketDataError as e:
            rec = ledger.log_decision("buy", "refused", reason, symbol=symbol, usd=usd_amount,
                                      refusal=f"no price: {e}", round_id=_round())
            return {"filled": False, "refusal": rec["refusal"]}
        refusal = gate.check_buy(state, decisions, equity, usd_amount, _round())
        if refusal:
            ledger.log_decision("buy", "refused", reason, symbol=symbol, price=price,
                                usd=usd_amount, refusal=refusal, round_id=_round())
            return {"filled": False, "refusal": refusal}
        fee = usd_amount * gate.FEE_RATE
        qty = (usd_amount - fee) / price
        state["cash"] -= usd_amount
        state["fees_paid"] += fee
        state["position"] = {"symbol": symbol, "qty": qty, "entry_price": price,
                             "cost_usd": usd_amount}
        ledger.save_state(state)
        ledger.log_decision("buy", "filled", reason, symbol=symbol, price=price, size=qty,
                            usd=usd_amount, fee=fee, round_id=_round())
        return {"filled": True, "symbol": symbol, "price": price, "qty": qty, "fee": fee,
                "cash": state["cash"]}


@server.tool()
def sell_all(reason: str) -> dict:
    """Close the whole open position at the latest price. Must pass the risk gate."""
    with ledger.locked():
        state = ledger.load_state()
        decisions = ledger.read_jsonl(ledger.DECISIONS)
        pos = state["position"]
        symbol = pos["symbol"] if pos else None
        refusal = gate.check_sell(state, decisions, _round())
        price = None
        if not refusal:
            try:
                price = market.latest_price(symbol)
            except market.MarketDataError as e:
                refusal = f"no price: {e}"
        if refusal:
            ledger.log_decision("sell_all", "refused", reason, symbol=symbol, price=price,
                                size=pos["qty"] if pos else None, refusal=refusal,
                                round_id=_round())
            return {"filled": False, "refusal": refusal}
        gross = pos["qty"] * price
        fee = gross * gate.FEE_RATE
        state["cash"] += gross - fee
        state["fees_paid"] += fee
        state["position"] = None
        ledger.save_state(state)
        ledger.log_decision("sell_all", "filled", reason, symbol=symbol, price=price,
                            size=pos["qty"], usd=gross, fee=fee, round_id=_round())
        return {"filled": True, "symbol": symbol, "price": price, "proceeds": gross - fee,
                "fee": fee, "pnl": gross - fee - pos["cost_usd"], "cash": state["cash"]}


@server.tool()
def hold(reason: str) -> dict:
    """Do nothing this round, but log why."""
    with ledger.locked():
        state = ledger.load_state()
        pos = state["position"]
        price = None
        if pos:
            try:
                price = market.latest_price(pos["symbol"])
            except market.MarketDataError:
                pass
        ledger.log_decision("hold", "logged", reason, symbol=pos["symbol"] if pos else None,
                            price=price, size=pos["qty"] if pos else None, round_id=_round())
    return {"logged": True}


if __name__ == "__main__":
    server.run()
