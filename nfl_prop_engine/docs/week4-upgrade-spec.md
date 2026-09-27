# NFL Prop Engine — Week 4 Upgrade Spec

Written by Dan, 2026-09-27, after both Week 3 accumulators lost. Saved here
so the spec driving `config.py`, `leg_gates.py`, `accumulator.py`,
`prop_bets_log.py`, `fetch_bet365.py`, and `analyst_sweep.py` is
version-controlled next to the code it drives, not only in an external doc.

## Context and goal

Upgrade the existing `nfl_prop_engine` so Week 4 picks are overs-only,
priced against the US market, captured midweek, and logged for review.

- **Existing code:** the `nfl_prop_engine` module in the `pitchside-backend`
  repo, branch `claude/nfl-prop-ranking-engine-kth7z5`. Extend it; don't
  rewrite it.
- **Why:** both Week 3 accumulators (27 Sep 2026) lost. The failures were:
  - under legs that depended on game script (Pollard, Mayfield, Javonte Williams)
  - lines taken on Sunday after they had moved, or where bet365 sat well
    above the US market (Maye 222.5 vs 214.5, Garrett Wilson 76.5 vs 65.5,
    Pollard 61.5 vs 48.5)
  - filler legs added just to reach six
  - picks leaning on a single analyst
- **Goal:** a weekly report of over candidates that pass every gate, an
  accumulator builder that never pads, and a results log that measures
  closing line value (CLV).

## Scope

**In scope:** overs-only filtering, midweek line snapshots, US-consensus vs
bet365 comparison, leg quality gates, an accumulator builder, a results log
with settlement and CLV, and a weekly report.

**Out of scope:** placing bets or connecting to any bookmaker account;
scraping bet365 (bet365 lines come in through a manual CSV import instead);
scraping sites that block automated access or sit behind paywalls (analyst
picks come from the analyst sweep, Requirement 7); automated weather data
(phase 2); hosting the scheduler (this spec only supplies commands/cron
examples).

## Requirement 1: Overs only

Candidates, report, and accumulator builder contain overs only by default.
`sides` defaults to `["over"]`; unders dropped before ranking.
`unders_watchlist` defaults to `false` — if `true`, unders get their own
report section, never the accumulator builder. Markets in scope: passing
yards, rushing yards, receiving yards, receptions, rushing attempts, plus
the existing defensive props (overs only). One-play markets (longest rush,
longest reception, anytime TD) excluded from accumulators by default
(`one_play_markets: false`) — a single play decides them.

## Requirement 2: Midweek line snapshots

Picks come from the Wednesday snapshot, not Sunday prices. Every snapshot
stored so line movement and closing lines can be measured.

| Snapshot | When (UK time) | Purpose |
|---|---|---|
| Opener | Tuesday 18:00 | Baseline once prop markets post |
| Midweek | Wednesday 18:00 | Main pick window |
| Friday | Friday 20:00 | Re-check after final injury reports |
| Sunday | Sunday 12:00 | Last check before the early games |
| Close | 30 min before each kickoff | Closing line for CLV |

One row per book per player-market per snapshot: UTC timestamp, event id,
book, market, player, line, over price, under price. Not-yet-posted
markets recorded as such and retried next snapshot. Player names
normalized across books via a mapping table. Credit cost
(events × markets × regions) printed and the run stopped if it exceeds
`credit_cap`. Times displayed in `timezone` (default Europe/London).

## Requirement 3: US consensus vs bet365

An over only qualifies if bet365's line is no worse than the US market by
more than a small tolerance, at a price of at least 1.80 (~4/5).

- **US consensus line:** median across US books (DraftKings, FanDuel,
  BetMGM, Caesars, others). Needs ≥2 books, else flagged a thin market.
- **Fair probability:** de-vig each book's over/under pair, then average
  across books at the consensus line: `p_over = (1/o_over) / (1/o_over + 1/o_under)`.
- **bet365 lines:** check whether The Odds API returns bet365 NFL player
  props on Dan's plan first; if not, import `bet365_week{N}.csv` (player,
  market, line, over price) by hand. Fractional odds (e.g. 20/23) must parse.
- **Line gate:** pass only if bet365 line ≤ consensus + `line_threshold`
  (2.0 yards / 0.0 counts).
- **Price gate:** bet365 over price ≥ `min_price_decimal` (default 1.80).
- **Movement flag:** flag (don't fail) any prop whose consensus line moved
  ≥3 yards (≥1 for counts) since the opener.

## Requirement 4: Leg quality gates

A leg must pass every gate to reach the accumulator builder. A failed gate
excludes the leg; the report states which gate failed and why.

| Gate | Check | Default pass rule | Data |
|---|---|---|---|
| Form | Last 6 games, reaching into prior season if needed | Hit rate vs line ≥50% and median ≥ line | nflverse weekly stats |
| Outlier | Drop the best game from those 6 | Remaining average ≥90% of the line | nflverse weekly stats |
| Role | Snap and route share now vs prior season | Flag as role change if moved ≥15 points; manual review | nflverse snap counts |
| Matchup | Opponent's allowed yards in that stat vs league average | Opponent at or worse than average | nflverse play-by-play |
| Game script | Spread and total vs the stat | Rushing overs: favored or a dog by ≤3. Passing/receiving overs: a dog, or total ≥45 | Odds API spreads/totals |
| Injury | Player status; teammates out who change volume | Player not Q/D/Out; teammate absences flagged | nflverse injuries |
| Sources | Independent analysts backing the over | ≥2 (`min_sources`), from the analyst sweep, dissent flagged | Analyst sweep (Req. 7) + manual CSV |
| Weather (phase 2) | Sustained wind at outdoor games | Flag passing/receiving overs at ≥15 mph | Weather API (later) |

The outlier gate is the Jahmyr Gibbs check: 104 yards/game from one
156-yard game and one 52-yard game is not a trend.

## Requirement 5: Accumulator builder

Only legs that passed every gate; never pads to reach a target size.

- Maximum 6 legs (`max_legs`). Only 4 pass → build a 4-fold. Fewer than 3
  pass → singles, or recommend no bet.
- Maximum 2 legs per game (`max_legs_per_game`). Same-game pairs must rely
  on the same game script (e.g. QB passing over + his receiver's receiving
  over) and are marked as bet-builder legs (bet365 prices those separately).
- Show combined odds and a rough hit probability: the product of each leg's
  fair probability, labelled as assuming independence.
- Flat stake from config (`stake_gbp`, default £5). Stake never rises after a loss.

## Requirement 6: Results log, settlement, CLV

Every leg placed is logged, settled automatically, scored on CLV. After
4-6 weeks, this tells us whether the process works, faster than wins and
losses alone.

Table `prop_bets` (SQLite): week, placed_at; game, player, market, side;
book_line, book_price; consensus_line_at_bet, fair_prob_at_bet;
closing_consensus_line, closing_fair_prob; actual_stat, result; acca_id,
bet_builder_group, sources.

Settlement pulls final stats from nflverse; voids a leg if the player
didn't take part (matching bet365's own rule). Line CLV for overs =
closing consensus line − the line bet (positive means we beat the close).
Weekly review: hit rate, average line CLV, flat-stake P&L, split by market
type and gate flags, rolling 4-week and season totals.

## Requirement 7: Analyst sweep

Before the report is finalized, the engine searches for published analyst
picks on every game with a surviving candidate, recording who is for and
against each over.

- **How:** call the Claude API with web search once per GAME, not once per
  player, to keep cost down. Ask for that week's published player-prop
  picks for that game, as strict JSON: outlet, analyst, player, market,
  side, line, price, book if stated, publish date, URL, any stated track record.
- **Sources to cover:** Action Network, Covers, SI, FanDuel Research, Sharp
  Football Analysis, SportsBettingDime, SBR, Fantasy Life, VSiN, RotoWire,
  ESPN, and projection models such as Dimers or Action's player projections.
- **Matching:** map each pick to a candidate by player, market, side. A
  pick at a different line still counts if within tolerance.
- **Independence:** count each analyst once, even when syndicated (an
  Action Network piece republished on Yahoo is one source). Ignore picks
  older than 7 days or from a previous week.
- **For and against:** Sources gate needs ≥2 independent sources on the
  over. Any analyst backing the under is shown next to the leg with a
  one-line reason, and the leg is marked contested for manual review — the
  Week 3 Mayfield lesson.
- **Crowding flag:** flag props backed by ≥4 outlets — heavy public
  backing often means the line has already moved (Garrett Wilson, Week 3).
- **Analyst scorecard:** sources logged per leg; the weekly review adds
  each analyst's hit rate and line CLV once they have ≥5 logged picks. Over
  time, weight analysts by record, not reputation.
- **Guardrails:** skip sites that block automated access or sit behind
  paywalls (record that a pick exists but not its side for a paywalled
  source). Respect `analyst_sweep.max_games` and a spend cap.
- **Manual edits:** Dan can add or remove sources in
  `analyst_sources_week{N}.csv` before the report runs.

## Outputs, commands and config

Seven commands: `snapshot`, `import-bet365`, `analysts`, `report`,
`record`, `settle`, `review`. Each report lists over candidates ranked,
with the bet365 line/price, US consensus (and book count), movement since
opener, and every gate's pass/fail with a one-line reason.

```
python -m nfl_prop_engine snapshot --label opener|midweek|friday|sunday|close
python -m nfl_prop_engine import-bet365 bet365_week4.csv
python -m nfl_prop_engine analysts --week 4
python -m nfl_prop_engine report --week 4
python -m nfl_prop_engine record --week 4 --acca <legs>
python -m nfl_prop_engine settle --week 4
python -m nfl_prop_engine review
```

## Validation, tests and acceptance criteria

Done when a Week 3 replay catches the bad legs actually bet and Week 4
runs end to end from a Wednesday snapshot.

**Week 3 replay:** fixture data from the Week 3 numbers above, no
historical API calls. Must show Maye Over 222.5, Garrett Wilson Over 76.5,
and Pollard Over 61.5 all failing the line gate, and no unders in the output.

**Acceptance criteria:** Week 4 report generates from the Wednesday
snapshot with ≥2 US books per included market; no unders appear while
`sides` is `[over]`; every excluded leg shows the gate it failed and why;
bet365 CSV import accepts fractional odds; the Close snapshot and
settlement fill in CLV for every logged leg; the Week 3 replay reproduces
the three line-gate failures; the analyst sweep returns picks with URLs
for every candidate game, counts syndicated articles once, and marks legs
with any analyst on the under as contested; the weekly review shows each
analyst's hit rate once they have ≥5 logged picks.

## Open questions (resolved during implementation)

1. **Does The Odds API return bet365 NFL player props?** Inconclusive from
   public docs (player-prop markets are "mainly limited to US sports"
   bookmakers per their own docs) — genuinely untested live since the
   account was out of credits when this was built. Manual CSV import is
   the primary path either way, not a fallback.
2. **Market keys and credit cost per event?** Empirically ~8 credits/event
   for the 10 currently-configured markets at `region=us` (from real
   workflow logs), not the naive 10 the markets×regions formula would
   suggest — the API appears to charge for markets actually returned, not
   requested.
3. **Where do snapshots run?** GitHub Actions, fixed time slots (Dan's
   choice) — 4 snapshots as simple fixed-time crons; Close as a few fixed
   crons tuned to common kickoff windows rather than exact per-game timing.
4. **Game-script gate: exclude or flag?** Exclude, per the spec's own default.
5. **Analyst sweep model/key/budget?** Claude Sonnet 5, `ANTHROPIC_API_KEY`
   as a separate repo secret (separate Anthropic account/billing from
   whatever built this code), $15/month spend cap.
