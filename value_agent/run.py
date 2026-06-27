"""
Weekly runner — entry point for the value-bet agent.

Usage
-----
    # Run a full scan and print the card:
    python -m value_agent.run scan

    # Record a bankroll deposit (top up the pot):
    python -m value_agent.run deposit 200

    # Settle a bet result (bet_id from the log):
    python -m value_agent.run settle <bet_id> win|loss|void

    # Record closing Pinnacle odds and compute CLV:
    python -m value_agent.run clv <bet_id> <closing_odds>

    # Print CLV summary across all bets:
    python -m value_agent.run clv-summary

    # Verify which bookmakers are live (uses one API credit):
    python -m value_agent.run verify

Environment variables required
------------------------------
    ODDS_API_KEY      — OddsPapi / The Odds API key
    ANTHROPIC_API_KEY — for LLM commentary (optional; card still prints without it)
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

from .api_client import OddsAPIClient, OddsAPIError
from .commentary import generate_commentary
from .config import LOG_DB_PATH
from .logger import (
    clv_summary,
    get_balance,
    init_db,
    log_bet,
    record_deposit,
    settle_bet,
    update_closing_odds,
)
from .output import format_card, to_dict
from .scanner import scan, verify_books
from .staking import BettingSlip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def cmd_scan(args: argparse.Namespace) -> None:
    init_db()
    balance = get_balance()

    client = OddsAPIClient()
    log.info("Starting weekly scan …")

    try:
        result = scan(client, balance)
    except OddsAPIError as exc:
        log.error("Scan aborted: %s", exc)
        sys.exit(1)

    if result.bankroll_paused:
        print(f"\n⛔  {result.pause_reason}\n")
        sys.exit(0)

    # ── commentary ─────────────────────────────────────────────────────────
    total_stake = sum(s.stake for s in result.slips)
    commentary = generate_commentary(result.slips, total_stake)

    # ── print card ─────────────────────────────────────────────────────────
    scan_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    card = format_card(
        slips=result.slips,
        commentary=commentary,
        balance=balance,
        scan_date=scan_date,
        active_leagues=result.active_leagues,
        live_books=result.live_books,
        quota_remaining=result.quota_remaining,
    )
    print(card)

    # ── log bets ───────────────────────────────────────────────────────────
    if not args.dry_run and result.slips:
        print("\nLogging bets to DB …")
        running_balance = balance
        for slip in result.slips:
            running_balance -= slip.stake
            if slip.slip_type == "single":
                leg = slip.legs[0]
                log_bet(
                    scan_date=scan_date,
                    league=leg.league,
                    fixture=leg.fixture,
                    fixture_id=leg.fixture_id,
                    sport_key=_league_to_sport_key(leg.league),
                    market=leg.market,
                    selection=leg.selection,
                    book=leg.book,
                    odds_taken=leg.soft_odds,
                    true_p=leg.true_p,
                    fair_odds=leg.fair_odds,
                    edge_pct=leg.edge * 100,
                    stake=slip.stake,
                    slip_type=slip.slip_type,
                    running_bankroll=running_balance,
                )
            else:
                # Log each leg of a multi separately so CLV can be tracked
                for leg in slip.legs:
                    log_bet(
                        scan_date=scan_date,
                        league=leg.league,
                        fixture=leg.fixture,
                        fixture_id=leg.fixture_id,
                        sport_key=_league_to_sport_key(leg.league),
                        market=leg.market,
                        selection=leg.selection,
                        book=leg.book,
                        odds_taken=leg.soft_odds,
                        true_p=leg.true_p,
                        fair_odds=leg.fair_odds,
                        edge_pct=leg.edge * 100,
                        stake=0.0,   # stake is on the slip, not individual legs
                        slip_type=slip.slip_type,
                        running_bankroll=running_balance,
                    )
        print(f"Logged {len(result.slips)} slip(s). Balance after staking: £{running_balance:.2f}")
    elif args.dry_run:
        print("\n[DRY RUN — no bets logged to DB]")


def cmd_deposit(args: argparse.Namespace) -> None:
    init_db()
    amount = float(args.amount)
    new_balance = record_deposit(amount, note="manual top-up")
    print(f"Deposit £{amount:.2f} recorded. New bankroll: £{new_balance:.2f}")


def cmd_settle(args: argparse.Namespace) -> None:
    init_db()
    result_str = args.result.lower()
    if result_str not in ("win", "loss", "void"):
        print("result must be one of: win, loss, void")
        sys.exit(1)
    new_bal = settle_bet(int(args.bet_id), result_str)
    print(f"Bet #{args.bet_id} settled as {result_str}. Balance: £{new_bal:.2f}")


def cmd_clv(args: argparse.Namespace) -> None:
    init_db()
    clv = update_closing_odds(int(args.bet_id), float(args.closing_odds))
    sign = "+" if clv >= 0 else ""
    print(f"Bet #{args.bet_id} CLV: {sign}{clv * 100:.2f}%")


def cmd_clv_summary(_args: argparse.Namespace) -> None:
    init_db()
    stats = clv_summary()
    if stats["count"] == 0:
        print("No bets with closing odds recorded yet.")
        return
    print(f"\nCLV summary ({stats['count']} bets with closing data)")
    print(f"  Average CLV         : {stats['avg_clv'] * 100:+.2f}%")
    print(f"  Avg edge at rec     : {stats['avg_edge_at_rec']:.2f}%")
    print(f"  Positive CLV rate   : {stats['positive_clv_rate'] * 100:.0f}%")
    print()
    if stats["avg_clv"] < 0:
        print("  ⚠  Negative average CLV — the agent is not finding genuine value.")
        print("     Stop, do not lower the threshold or increase stakes.")


def cmd_verify(_args: argparse.Namespace) -> None:
    client = OddsAPIClient()
    try:
        live_soft = verify_books(client)
        print(f"\nSharp books confirmed: pinnacle, betfairix")
        print(f"Live soft books ({len(live_soft)}): {', '.join(live_soft)}")
    except OddsAPIError as exc:
        print(f"Verification failed: {exc}")
        sys.exit(1)


def _league_to_sport_key(league_name: str) -> str:
    from .config import LEAGUES
    for k, v in LEAGUES.items():
        if v == league_name:
            return k
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="UK Football Value-Bet Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    p_scan = sub.add_parser("scan", help="Run the weekly scan")
    p_scan.add_argument(
        "--dry-run", action="store_true",
        help="Print card without logging bets to DB"
    )
    p_scan.set_defaults(func=cmd_scan)

    # deposit
    p_dep = sub.add_parser("deposit", help="Record a bankroll deposit")
    p_dep.add_argument("amount", type=float, help="Amount in £")
    p_dep.set_defaults(func=cmd_deposit)

    # settle
    p_settle = sub.add_parser("settle", help="Record a bet result")
    p_settle.add_argument("bet_id", help="Bet ID from the log")
    p_settle.add_argument("result", choices=["win", "loss", "void"])
    p_settle.set_defaults(func=cmd_settle)

    # clv
    p_clv = sub.add_parser("clv", help="Record closing odds and compute CLV")
    p_clv.add_argument("bet_id", help="Bet ID from the log")
    p_clv.add_argument("closing_odds", type=float, help="Pinnacle closing decimal odds")
    p_clv.set_defaults(func=cmd_clv)

    # clv-summary
    p_clvs = sub.add_parser("clv-summary", help="Print CLV summary stats")
    p_clvs.set_defaults(func=cmd_clv_summary)

    # verify
    p_verify = sub.add_parser("verify", help="Verify available bookmakers")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
