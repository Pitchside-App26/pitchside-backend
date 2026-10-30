"""Record one equity point (mark to market). run_round.sh calls this after each round."""
import ledger
import market

with ledger.locked():
    state = ledger.load_state()
    ledger.save_state(state)  # creates state.json on the first run
    pos = state["position"]
    try:
        value = pos["qty"] * market.latest_price(pos["symbol"]) if pos else 0.0
        ledger.log_equity(state["cash"] + value, state["cash"], value)
        print(f"equity ${state['cash'] + value:.2f}")
    except market.MarketDataError as e:
        print(f"equity not recorded: {e}")
