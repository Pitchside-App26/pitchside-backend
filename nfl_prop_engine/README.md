# NFL Prop Ranking Engine

Weekly pipeline: pull nflverse stats + this week's schedule, pull live prop
lines from The Odds API, blend a projection per player/stat with
early-season shrinkage and opponent adjustment, rank props by
standard-deviation-scaled edge, print a markdown table, and log every run to
SQLite so the ranking's track record can actually be checked later.

## Setup

```
pip install -r requirements.txt
cp .env.example .env   # fill in ODDS_API_KEY
```

Get the key from **the-odds-api.com** -- not theoddsapi.com, a similarly
named but different product with no NFL data on its free tier.

## Running it

```
python run_weekly.py --raw          # step 1: matched player+line table only, no projection math
python run_weekly.py --cache        # replay cached odds JSON (see below) instead of live calls
python run_weekly.py                # live run: fetches odds, ranks, prints, logs to SQLite
python run_weekly.py --season 2024 --week 5   # backtest a specific past week
```

Follow the spec's suggested build order: run `--raw` first and eyeball that
the matched player/line/team rows look right before trusting the ranked
output.

`verify_markets.py` is a separate one-time tool -- see "What still needs
live verification" below.

## Grading past weeks (grade_results.py)

```
python grade_results.py            # grade every ungraded logged week, then report
python grade_results.py --report   # skip grading, just report on what's already graded
```

`results_log.py` has logged every ranked prop since the very first real
run, but until this existed nothing ever read `actual_value` back in --
"is this ranking any good" was an unanswered question no matter how many
weeks accumulated. This closes that loop: pulls real final stats the same
way `run_weekly.py` does (same `fetch_all_stats()` / play-by-play fallback,
no separate unverified data path), fills in `actual_value` for every prop
whose game has a final score, and reports hit rate broken down by stat,
confidence tier, and `|edge_score|` bucket -- not just one overall number,
which grading week 1 by hand already proved can be badly misleading on its
own (see "Week 1 grading" below).

A player with a completed game but no row in that week's stats is graded
as a hard 0 (they recorded none of that stat) -- this engine has no
injury/inactive feed yet, so a genuinely-inactive player and a
zero-production active one currently grade the same way. Known
simplification, not a bug; revisit if it turns out to matter.

Intended to run on a schedule (see below) the same way the ranking run
does, so the track record builds up automatically week over week.

### Week 1 grading (2026-09-15, real results)

First real backtest, graded against KC's actual 31-10 win over DEN and
NYG's 28-20 win over DAL: 345 logged rows, 46.9% hit rate overall (161
hit / 182 miss). That overall number is noisy in a specific, informative
way, not just "not great":

- **10% of the props were individual-defender "under 0.5 sacks" bets**,
  which structurally hit most of the time regardless of the model (most
  role players record zero sacks in a given game -- low variance inflates
  `edge_score` for these, see `game_context.py`'s note on why defensive
  stats don't get the same adjustment yet).
- **Every single passing_yards and completions prop missed (0% on both)**
  -- real, not a bug (checked the underlying rows directly): all three
  quarterbacks that week (Mahomes, Nix, Dak, Dart) landed on the wrong side
  of their number, in both directions -- the "over" picks missed low, the
  "under" pick missed high. One bad week for a whole stat category, not
  evidence the category is broken.
- **`|edge_score|` buckets are NOT cleanly monotonic** (0.50-1.00 graded
  worse than 0.25-0.50) -- with an n this small and this many dev-test
  re-runs of the same single week mixed into the numbers (see the report's
  own duplicate-run caveat), this is not yet a real signal either way.

Bottom line: one graded week proves nothing statistically, which is the
point of building this now rather than trusting the ranking on vibes --
the real test is whether the hit rate (and the edge-bucket monotonicity)
looks any different after several genuine, independent weekly runs.

## The results page (site/)

Every run also writes `site/data.json` alongside the static `site/index.html`
page, which reads it client-side and renders a ranked, filterable mobile-first
card list (search by player, filter Over/Under, sort by edge/hit-rate/player).
Nothing server-side -- it's a plain static page.

Each prop also carries a "Why this number?" toggle -- `explain.py` turns the
projection engine's actual intermediate numbers (current/prior-season
averages, the blend weighting, the opponent-matchup adjustment, or the
draft-analog pool for rookies) into a plain-English sentence or two. It's
built directly from real values the engine already computed, not inferred
after the fact from the final projection.

**Deployment**: `.github/workflows/nfl-prop-rankings.yml` uploads `site/` as
a GitHub Pages artifact after every run (scheduled or manual) and deploys it.
One-time setup required: in the repo's Settings -> Pages, set **Source** to
**GitHub Actions** (there's no API for this, it's a manual toggle). After
that, every run automatically republishes the page -- no separate step, no
extra credits, it's just the last stage of the same workflow.

The `site/data.json` committed to git is a real-data sample from an actual
run, kept as a local dev fixture / fallback so the page shows something if
opened before CI has run -- it is NOT kept in sync with the live deployed
page (the workflow generates a fresh one per run but only uploads it to
Pages, it doesn't commit it back to the branch). Don't be surprised if they
differ.

## What was verified against real data during development

This environment's network egress couldn't reach the-odds-api.com at all
(confirmed directly -- both `requests` and a browser-fetch tool were
blocked), but nflverse's own data releases on GitHub were reachable, so
everything below was checked against the actual data rather than assumed:

- **`nfl_data_py.import_weekly_data()` does NOT include defensive stats.**
  The spec's premise -- that nflverse bundles offense/defense/kicking into
  one file -- turned out to be false for the installed package (0.3.3):
  inspecting its source shows it reads a single
  `player_stats_{year}.parquet` asset, and pulling it confirmed the columns
  are offense-only (`passing_yards`, `receiving_yards`, etc; no
  `def_tackles` or similar even for rows where `position` is `CB`/`DE`/etc).
  Defense and kicking are published as **separate assets in the same
  release** (`player_stats_def_{year}.parquet`,
  `player_stats_kicking_{year}.parquet`). `fetch_stats.py` pulls the defense
  one directly with `pandas.read_parquet()` since `nfl_data_py` doesn't
  expose it. Confirmed real columns: `def_tackles`, `def_tackles_solo`,
  `def_sacks`, `def_interceptions`, `def_pass_defended`, `def_tds`, etc.
- **The defense stats file has no `opponent_team` column** (unlike the
  offense file, which does). `opponent_stats.py`'s `add_opponent_column()`
  joins defensive player-weeks to the schedule to recover who they played,
  which is needed before "opponent allowed" rates can be computed for
  defensive props the same way they're computed for offensive ones.
- **`nfl_data_py.import_schedules()` failed in this sandbox** (403 from
  `habitatring.com`, likely this environment's network policy rather than a
  real-world problem) but the same data is published as a GitHub release
  asset (`schedules/games.parquet`) with an identical schema
  (`spread_line`, `total_line`, `roof`, etc, confirmed by downloading it).
  `fetch_schedule.py` tries `import_schedules()` first and falls back to
  that asset automatically if it fails, so this is resilient either way.
- **`import_draft_picks()`** confirmed to carry `round`/`pick`/`position`/
  `college`/`age` plus career box-score totals (not college stats) -- no
  more than the spec assumed, joined to weekly data via `gsis_id` ==
  `player_id`.
- **nflverse's pre-aggregated `player_stats` release can lag real time by
  more than a full season.** Found this the hard way running against an
  actual live week: `player_stats_2025.parquet` and `player_stats_2026.parquet`
  (and their `_def` counterparts, and even the combined all-seasons
  `player_stats.parquet`) all 404 or stop at 2024, despite the live
  schedule and odds feeds already showing played 2026 games. The
  underlying raw `play_by_play_{season}.parquet` release did NOT have this
  gap -- confirmed current through the actual live week. `derive_stats_from_pbp.py`
  recomputes the same per-player weekly offense/defense totals directly
  from play-by-play (passing/rushing/receiving yards and TDs, completions,
  sacks including correctly-credited half-sacks, combined tackles,
  interceptions) as an automatic fallback whenever the pre-built file
  isn't available for a season yet. `fetch_offense_weekly()` /
  `fetch_defense_weekly()` try the pre-built file per season first and only
  fall back per season, so a gap in one season doesn't affect another.
  Sanity-checked against real 2026 week-1 data: sack totals correctly
  split into 1.5/2.0 credits for shared sacks, and passing/receiving lines
  matched real, plausible box scores.
- **Formula bug found via that same real run:** `project_veteran()`'s
  `last5_avg` fell back to `current_season_avg` (always 0 with no real
  games behind it) whenever a player had zero games in the current season
  -- true for literally every player before their first game of a new
  season. That silently cut the blended baseline roughly in half (a real
  veteran QB with a full healthy prior season projected at ~half his real
  average). Fixed to fall back to `blended_season_avg` instead, which
  already properly incorporates the prior season. Covered by
  `test_project_veteran_zero_current_games_uses_prior_season_not_zero`.
- **Second formula bug, found from a real user report and confirmed
  against real data**: `last5_avg` was the RAW, unshrunk average of
  whatever current-season games existed, then blended 50/50 into
  `baseline` alongside `blended_season_avg` -- which already properly
  shrinks a thin current-season sample toward the prior season. The result:
  a small-sample outlier counted TWICE, once correctly diluted inside
  `blended_season_avg`, once at full raw weight as "recent form". Real
  example that surfaced it: Drake Maye threw 0.47 INT/game across all 17
  games last season, then 3 INTs in his one game so far this season --
  confirmed directly against his real logged numbers, this formula
  projected ~2.0 INTs, nearly double a properly regressed estimate. Fixed
  by shrinking `last5_avg` the same way `blended_season_avg` already is
  (same `k`, keyed on the number of games actually in the last-5 window)
  -- with 5 or fewer current-season games, "recent form" and "season
  average" are the same games and now correctly collapse to the same
  shrunk number instead of double-counting; the two only diverge once a
  player has genuinely played more than 5 games, which is exactly when a
  real hot/cold streak should be able to move the projection. Covered by
  `test_project_veteran_one_bad_game_does_not_double_count_against_a_real_history`
  and `test_project_veteran_recent_form_can_still_diverge_past_five_games`.
- **The Odds API's `/events` list call and its credit formula**
  (`markets_requested x regions_requested`) were confirmed via its public
  docs through search (the domain itself was unreachable directly).
- The core `projection_engine.py` formula (shrinkage blend, opponent
  adjustment, rookie draft-analog path) was run end-to-end against real
  2024 nflverse data as a sanity check, not just unit tests -- e.g. the
  opponent-allowed-sacks table correctly surfaced Chicago as the
  league's most sacks-allowed team for that season, which matches what
  actually happened (a widely-known bad offensive line year), not because
  that number was hand-picked.

## Market keys: now live-verified (as of 2026-09-13)

`verify_markets.py` was run for real (via the `verify-odds-markets.yml`
GitHub Actions workflow, since this sandbox can't reach the-odds-api.com
directly) against 3 games kicking off later that same day -- as strong a
test as possible, not a "too early, no props posted yet" false negative:

| Market key | Result |
|---|---|
| `player_pass_yds`, `player_pass_tds`, `player_pass_completions`, `player_pass_interceptions`, `player_rush_yds`, `player_rush_attempts`, `player_reception_yds`, `player_receptions` | **Confirmed working** -- real data on all 8 |
| `player_tackles_assists` (combined tackles) | **Confirmed working** |
| `player_sacks` | **Confirmed working** |
| `player_defensive_interceptions` | **Confirmed NOT offered** by any book on any of the 3 games checked -- removed from `config.py`. Apparently no book on this API offers a "will this defender record an interception" prop. |

10 of 11 configured markets are real and working. The one dropped market
was already the least-confident guess when this was built. Re-run
`verify_markets.py` occasionally if you want to check whether a defensive
-interceptions-style market appears later, or whenever adding a new market
key to `config.py`.

Still worth knowing:
- **The response shape `fetch_odds.parse_event_odds()` expects**
  (`bookmakers[].markets[].outcomes[].description` as the player name,
  `.point` as the line) matches the standard v4 player-props shape and is
  implicitly confirmed by `verify_markets.py` succeeding against real
  responses, but `run_weekly.py`'s full pipeline (matching, projecting,
  ranking real odds end to end) still hasn't been run against live data.
- Passes defended is still commented out in `config.py` (not checked --
  uncommon enough on this API that it likely isn't worth a market-key
  guess without evidence).

## Injury status and receiving usage (fetch_injuries.py, fetch_receiving_usage)

Two more facets from the same review, both CONFIRMED against real 2026
data before being wired in:

- **Injury status** (`fetch_injuries.py`): `nfl_data_py.import_injuries()`
  returns one row per (player, week) -- already the week's final report,
  not a per-practice-day log needing deduplication (checked directly: 0 of
  182 week 1 players had more than one row). Real `report_status` values:
  `Out`, `Doubtful`, `Questionable`, or not on the report at all. A player
  listed **Out is excluded from the ranked output entirely** -- a prop for
  someone who isn't playing isn't a real recommendation, same reasoning as
  never showing a rookie projection with zero basis behind it.
  `Doubtful`/`Questionable` stay in, tagged with a visible badge and a
  caution line in the "why" explanation, so it's visible rather than
  silently baked into the number. Real example from week 1: Malik Nabers
  (NYG) was listed Questionable (knee) -- confirmed directly against the
  real injury report, not a hypothetical.
- **Receiving usage** (`fetch_stats.fetch_receiving_usage`): Next Gen
  Stats' `targets` and target-share data, added as **context only** --
  shown in the "why" explanation for receiving props (e.g. "Averaging 5.0
  targets/game this season"), NOT folded into the projection number
  itself. Usage-based projection is a real, separate piece of work that
  needs backtesting before it's trusted the way the existing formula is;
  this is the deliberately smaller, lower-risk first step.
  **Found and fixed a real data gotcha while verifying this**: NGS
  receiving data includes a `week=0` row per player alongside the real
  per-week rows -- a season-to-date aggregate, not an actual game. Left
  in, it would have silently double-counted into any per-player average
  (confirmed directly: week 0 and week 1 had identical row counts and, in
  week 1, identical target totals). Filtered out in
  `fetch_receiving_usage` before it reaches anything that averages by
  player.

Deliberately NOT built in this pass, with reasons:
- **Snap counts** -- verified real and populated
  (`nfl_data_py.import_snap_counts()`), but keyed by `pfr_player_id`
  rather than this engine's `gsis_id`, needing a crosswalk
  (`nfl_data_py.import_ids()`, also verified real -- 7,818 players have
  both IDs). Mostly duplicates what NGS targets already covers for
  receiving; lower priority until there's a concrete use (e.g. RB/QB
  usage, which NGS receiving doesn't cover) worth the join.
- **Red-zone / situational usage** -- derivable from the play-by-play file
  already in use (same way `derive_stats_from_pbp.py` works), but folding
  it into TD-likelihood props specifically doesn't have anywhere to land
  yet: `config.py`'s `OFFENSE_MARKETS` only tracks `passing_tds`, not
  `rushing_tds`/`receiving_tds` as markets at all. Wiring red-zone context
  in without a market to attach it to would be building ahead of what's
  actually rankable.
- **Weather** -- genuinely needs a new external data source (the schedule
  only has `roof`, dome vs. outdoor, not wind or temperature); an actual
  new integration rather than another nflverse pull. Deliberately skipped:
  only matters for outdoor games and mainly affects passing volume via
  wind, not worth a new account/API key relative to what's already
  shipped. Revisit if it turns out to matter after a few weeks of grading.

## Price-aware ranking (pricing.py)

Another gap from the same "what does the model actually know" review: the
odds API response was already carrying each outcome's American odds price
(`fetch_odds.py`'s `parse_event_odds()` was parsing it into every row all
along) -- `run_weekly.py` just discarded it, keeping only the line. That
meant `edge_pct`/`edge_score` measured distance from the number, never
whether the price on that side was any good. A prop could clear its line
by a mile and still be priced so that it isn't a good bet.

`pricing.py` adds:
- **`market_prob`**: the no-vig implied probability from BOTH sides'
  prices (the standard de-vig method: normalize each side's raw implied
  probability so they sum to exactly 100%, removing the book's edge).
- **`model_prob`**: this engine's own estimate, treating `edge_score` (how
  many standard deviations the projection clears the line by) as a z-score
  and taking its normal CDF. This is a real simplification -- actual stat
  distributions, especially low-count ones like sacks or interceptions,
  aren't perfectly normal -- and is exactly the kind of thing
  `grade_results.py` should eventually be used to check, the same way
  `SHRINKAGE_K` and the game-context weights are flagged as unvalidated
  starting points.
- **`value_pct`**: `model_prob - market_prob`, in percentage points. This
  is the number that actually answers "is this worth betting" -- and is
  now what `rank()` sorts by, falling back to `edge_score` only when a
  prop has no price data (e.g. old backtest rows from before this
  existed).

One side's price alone (`fetch_odds.py`'s old behavior, keeping only the
Over row) can't be de-vigged -- `pivot_over_under()` was added so both
sides' prices survive into one row per prop instead of the Under row being
thrown away immediately after parsing.

## Game-context adjustment (spread/total)

The projection engine used to know nothing about the specific game a player
was playing in -- only their own history and the opponent's season-long
tendency. `game_context.py` fixes the clearest gap that exposed: found by
grading real week 1 output against actual results (KC beat DEN 31-10;
J.K. Dobbins was projected for 76.8 rushing yards and actually got 36,
because Denver abandoned the run in a blowout -- a game-script effect the
engine had no way to see coming).

`fetch_schedule.py` was already pulling `spread_line` and `total_line` from
the schedule for every run -- confirmed by grep that nothing downstream
ever read them. That data is not new; it just wasn't wired to anything.

- **Sign convention CONFIRMED against real results**, not assumed:
  `spread_line` is from the home team's perspective, and *positive* means
  the home team is favored (the opposite of the common bettor-facing "-3"
  convention). Checked by correlating `spread_line` against actual
  home-team scoring margin across all 16 real games in 2026 week 1:
  +0.34, positive as expected. Getting this backwards would have silently
  flipped every adjustment below.
- **Two separate effects, not one**, because rushing and passing/receiving
  volume move in *opposite* directions off the same spread (a favorite
  protecting a lead runs more and throws less; a trailing underdog does the
  reverse):
  - `environment_factor`: this team's implied point total (half the game
    total, shifted by half their own spread) relative to the league-average
    team total for that week's real slate. Applied to both rush and pass
    stats -- a team implied for more points generally does more of
    everything.
  - `script_tilt`: -1..+1 from the team's own spread, clipped at 10 points.
    Boosts rushing volume and suppresses passing/receiving volume for
    favorites; the reverse for underdogs.
  - Both are capped-weight heuristics (`GAME_ENV_WEIGHT=0.2`,
    `GAME_SCRIPT_WEIGHT=0.15` in `config.py`), same unvalidated-starting-point
    status as `SHRINKAGE_K` -- real weights once there's enough graded data
    to tune against.
  - **Defensive stats are deliberately untouched for now.** A defender's
    tackle/sack opportunities scale with the *opponent's* plays run, not
    this team's own implied total -- a different, more complex relationship
    this first pass doesn't attempt to guess at.
- **Honest limit, checked against the Dobbins case that motivated this**:
  re-running the real numbers, this adjustment would have pulled his
  76.8-yard projection down to about 72.3 -- directionally right, nowhere
  near enough to flip the pick, because Denver was only a 2.5-point
  underdog on paper. The market itself didn't see that blowout coming
  either. This adjustment uses the same signal the market had, which is a
  real improvement over using none of it -- but it was never going to
  predict a blowout the spread itself didn't predict.

## Week 4 upgrade: accumulator engine (docs/week4-upgrade-spec.md)

A second, separate spec on top of the ranking engine above -- written
after both Week 3 accumulators lost. Full spec saved at
`docs/week4-upgrade-spec.md`; summary here.

**What it adds:** overs-only filtering (`accumulator.filter_by_side`,
enforced inside the accumulator builder itself, not just a config value
sitting unused -- an actual gap found while building the Week 3 replay
test), a manual bet365 CSV import (`fetch_bet365.py`, scraping bet365 is
out of scope per their ToS) compared against the US market's de-vigged
consensus (`pricing.py`'s decimal-odds helpers), seven leg-quality gates
(`leg_gates.py`: Line, Price, Movement, Form, Outlier, Matchup, Game
script, Injury, Sources), a no-padding accumulator builder
(`accumulator.py`), a separate `prop_bets` results log with settlement and
closing-line-value tracking (`prop_bets_log.py`), and an analyst sweep
(`analyst_sweep.py`) that calls the Claude API with web search once per
game to check what independent analysts are saying before a leg is trusted.

**The Week 3 replay is the spec's own acceptance test** (`tests/test_week3_replay.py`):
fixture data from the real numbers named in the spec confirms Maye Over
222.5, Garrett Wilson Over 76.5, and Pollard Over 61.5 all fail the line
gate (bet365's line had drifted too far from the US consensus on all
three), and that two deliberately-planted under legs (matching the "under
legs that depended on game script" failure named in the spec's own
postmortem) get excluded by the overs-only filter even when their own
gates look clean.

**Injury gate is deliberately stricter here than the main ranking page**:
any report status (not just Out) fails an accumulator leg, since a
real-money multi-leg bet has less tolerance for risk than a general
"worth looking at" ranked list.

**Deliberately incomplete, disclosed rather than hidden:**
- **Role and teammate-injury gates** are real comparison logic running on
  placeholder data -- real snap/route-share numbers need the
  `pfr_player_id` crosswalk work already deferred (see the injury/usage
  section above). Both currently pass through neutrally.
- **The CLI** the spec describes (`python -m nfl_prop_engine snapshot|
  import-bet365|analysts|report|record|settle|review`) isn't built as such.
  `report` and `analysts` run inside the weekly run (see "The accumulator
  report" below), and `record` is covered by bet-slip issues. `snapshot`,
  `settle` and `review` are still to do.
- **The five snapshot times** (opener/midweek/friday/sunday/close) aren't
  wired into a GitHub Actions cron yet. Close is the hard one: it needs to
  fire 30 minutes before EACH game's own kickoff, and NFL games kick off
  at several different times across a week -- the planned approach is a
  few fixed crons tuned to the common kickoff windows (1pm/4pm/8pm ET, Mon
  night) rather than exact per-game precision.
- **The analyst-scorecard** (each analyst's hit rate and line CLV once
  they have 5+ logged picks) needs the settlement/CLV data in `prop_bets`
  to actually accumulate over real weeks first -- the aggregation logic in
  `analyst_sweep.py` covers per-week independence/contested/crowding, not
  yet the historical per-analyst tracking the weekly review is meant to show.
- **The Odds API returning bet365 NFL player props at all** is unconfirmed
  -- their own docs suggest player-prop markets are "mainly limited to US
  sports" bookmakers, and the account was out of credits when this was
  built so it couldn't be tested live either way. The manual CSV import is
  built as the primary path, not a fallback, so this doesn't block anything.
- **The Claude API key powering the analyst sweep is a separate
  Anthropic account/billing** from whatever built this code -- its own
  `ANTHROPIC_API_KEY` repo secret, Sonnet 5, a $15/month spend cap set in
  `config.ANALYST_SWEEP`.

## The accumulator report (top of the results page)

Every weekly run (`run_weekly.py`) now ends with `acca_report.py`. It uses
data the run has already fetched, so it costs no extra Odds API credits.

For each over:
1. **US consensus.** The median line across US books, from every book's own
   line before the ranking collapses them to one. Fair probability is each
   book's over/under pair de-vigged, then averaged. Fewer than 2 books fails
   the **Market** gate (a thin market, so no target can be set).
2. **The target.** No feed carries UK bet365 NFL props, so the line and
   price gates become instructions on the page: bet only if bet365's line is
   at or below consensus + 2 (yards) or + 0 (counts), at 4/5 (1.80) or bigger.
3. **Gates, judged at that worst acceptable line:** Model (projection above
   it; an addition to the spec, so the page never suggests an over the engine
   projects under), Form, Outlier, Matchup, Game script, Injury. Teammates
   ruled out are a flag, not a failure.
4. **Accumulator builder, one per Sunday window** (`ACCA_WINDOWS`):
   - **Early** is the 1pm ET kickoffs and **late** is the 4:05/4:25pm ET
     kickoffs. The page shows UK times, converted from the real date, since
     UK and US clocks change a week apart.
   - Games outside both windows (London mornings, Thursday, Sunday and
     Monday nights) are ranked and logged but never used for an acca.
   - Each window takes up to 6 legs that passed every gate, max 2 per game.
   - **Fillers (Dan's call, 1 Oct, against the spec's never-pad rule):** if
     fewer than 6 pass, the acca is topped up with legs that failed exactly
     one gate, best projection margin first. Fillers are marked on the page
     with the gate they failed, and logged as `filler` so grading can show
     whether they drag results down. Legs with no consensus line are never
     fillers, since there's no bet365 target to give.
   - `FILL_WITH_NEAR_MISSES = False` restores the never-pad rule.
   - The page shows fair combined odds; bet365's acca price must beat them
     to be value.
5. **Analyst sweep**, up to `ANALYST_SWEEP["max_games"]` games (3, since the
   first live run cost $0.84 for one game), four at a time. It covers the
   games of the suggested legs first, alternating between the early and late
   windows, then other games with legs that survived the gates. Each leg shows who backs the over and who's against.
   Any analyst on the under marks the leg contested, and 4+ outlets marks it
   crowded.

**Analysts are a signal, not a gate (since 1 Oct).** The spec required 2+
independent analysts per leg. That's now off (`ANALYST_SWEEP["sources_gate"]
= False`):
- Searches miss under-covered props, so "found nothing" was being treated as
  "against".
- Analysts mostly cover the most efficiently priced lines.
- Nothing yet shows that analyst-backed legs win more.

Every evaluated leg goes to the `acca_legs` table with its gate result and
analyst counts. The Tuesday grading run fills in actual stats. The
accumulator section of `grade_results.py`'s report then compares hit rates
for passed vs failed legs, and for 2+ / 1 / 0 analysts, judged at the max
acceptable bet365 line. If backed legs clearly hit more over 4–6 weeks, set
`sources_gate` back to True.

The page also lists near misses (one failed gate) and every excluded over
with its reasons. It records the analyst sweep's estimated cost (also in the
Actions log) and whether bet365 showed up in the odds feed. If the report
crashes, the page says so and the rankings below still publish.

Expect "no bet" or a single some weeks. Every remaining gate still has to
pass, and on a real one-game test only 1 of 7 overs did.

Fixed while wiring this in:
- **Analyst picks could never match a leg.** Articles say "Receiving Yards"
  and "Over", while legs use `player_reception_yds` and `over`. Both are now
  normalized (`analyst_sweep.normalize_market` / `normalize_side`).
- **One syndicated article could count as several sources.** Unnamed-analyst
  picks now dedupe by outlet, then by URL.
- **A paused web-search turn (`stop_reason="pause_turn"`) read as "no
  picks".** It's now resumed.
- **Matchup failed on rounding noise.** A real NE run defence at 0.9998x
  failed as "better than average" while showing 1.00x. The gate now decides
  on the same 2-decimal figure it displays.

Cost: the sweep's real per-game cost is logged on each run (`Analyst sweep:
... estimated_cost_usd`). The $15/month cap in config is only a note: set the
actual limit on console.anthropic.com.

## Logging placed bets (bet-slip issues)

This replaces the spec's `record` command, because the bets actually placed
often differ from what the report recommended.

1. On GitHub, open a new issue with the **Bet slip** template, or any issue
   titled "Bet slip…". Attach a screenshot of the placed bet (bet365 → My
   Bets). Several screenshots are fine, and you can add them in a comment
   instead of the issue itself.
2. `.github/workflows/bet-slip.yml` reads the screenshots with the Claude API
   and comments with what it found: each bet's type, stake, odds and
   returns, plus each leg. It also lists anything that looks misread. Leg odds
   that don't multiply to the slip's total, or a stake × odds that doesn't
   match the returns, are the main misread signals.
3. Reply **confirm** to log it, **cancel** to discard it, or describe what's
   wrong in plain words (`leg 2 line is 64.5`, `week is 5`) and it reads the
   slip again. Nothing is logged until you confirm. Confirming again after a
   correction replaces what was logged, so a bet is never counted twice.
   Once a bet is settled, it can't be changed. GitHub can drop a reply's run
   when several arrive at once. If a reply gets no answer within a few
   minutes, send it again.

Logged bets go to `bet_slips` (one row per bet: stake, total odds, returns)
and `prop_bets` (one row per leg), both in `results_log.sqlite3`.

**The repo is public.** Only the repo owner's own issues and comments are
acted on; anyone else's are ignored, including images and anything that looks
like a draft. The screenshots and the logged bets are publicly visible,
though, so crop out balance, name and bet reference before attaching.

Not built yet:
- **Consensus line and fair probability at bet time** stay empty until the
  odds snapshots run (the Odds API account resets on 1 Oct). They're kept as
  columns so they can be backfilled from the midweek snapshot.
- **Settling whole bets.** Leg-level settlement exists (`settle_week`).
  Deciding each bet's result and returns from its legs (voids, bet builders)
  is part of the `settle` step.
- **Showing logged bets on the results page.** The page is published only by
  the rankings workflow. The committed `site/data.json` is stale, so this
  workflow deliberately doesn't republish the site.

## Design choices worth knowing about (not explicit in the spec)

- **Non-rookie players with a genuinely thin combined sample** (e.g. a
  2nd-year player with 1 prior-season game and 1 current-season game -- 2
  combined, below the 3-game bar, but not a true rookie either) still get
  the veteran-formula math run, just tagged `method="thin_sample"` /
  `confidence="low"` rather than diverted to the rookie-analog path, which
  the spec only defines for players with literally zero prior-season data.
- **Undrafted rookies** (no draft slot at all) fall back to using every
  rookie at the position as the analog pool, since "similar draft slot" is
  undefined without a slot. Tagged the same low-confidence way.
- **`season_std` when a player has <2 games in both seasons combined**
  (division-by-zero territory for the edge score) falls back to the
  league-wide median stdev for that stat, computed once per run
  (`league_fallback_std()`), rather than reporting a fake zero-width band.
- **Multiple books quoting different lines for the same prop**: consolidated
  by preferring a single fixed book (DraftKings) when it has a line,
  falling back to the median across books otherwise. Not specified by the
  spec -- revisit if book selection turns out to affect accuracy.
- **Hit rate** excludes exact pushes (games where the actual value equals
  the line) from both the numerator and denominator, matching how a real
  sportsbook push works, rather than counting a push as a loss.

## Files

| File | Step |
|---|---|
| `config.py` | shared constants; read this first -- it documents what's verified vs. guessed |
| `fetch_schedule.py` | step 1 |
| `fetch_odds.py`, `verify_markets.py` | step 2 |
| `fetch_stats.py` | step 3; also NGS receiving usage (targets/target share) |
| `fetch_injuries.py` | weekly injury report -- excludes OUT players, flags Questionable/Doubtful |
| `match_players.py`, `name_overrides.json` | step 4 |
| `opponent_stats.py`, `projection_engine.py`, `game_context.py` | step 5 |
| `explain.py` | turns a Projection's real intermediate numbers into the "Why this number?" text |
| `pricing.py` | American-odds price -> no-vig/model probability -> value_pct, used by step 6's ranking |
| `rank_props.py` | step 6 |
| `output.py` | step 7 |
| `results_log.py` | durable weekly logging (SQLite) for later grading |
| `grade_results.py` | fills in real outcomes and reports hit rate -- the "later" `results_log.py` was built for |
| `run_weekly.py` | orchestrator / CLI entrypoint |
| `tests/` | unit tests for the pure-logic pieces (projection math, matching, ranking) |
| `docs/week4-upgrade-spec.md` | the accumulator-engine spec below, saved in full |
| `fetch_bet365.py` | manual bet365 CSV import + fractional odds parsing |
| `leg_gates.py` | the 8 leg-quality gates (Line/Price/Movement/Form/Outlier/Matchup/Game script/Injury/Sources) |
| `accumulator.py` | no-padding accumulator builder, overs-only enforcement |
| `prop_bets_log.py` | separate `prop_bets` log: settlement, void handling, closing line value |
| `analyst_sweep.py` | Claude API + web search, once per game -- independent analyst picks, deduped and aggregated |
| `acca_report.py` | the weekly accumulator report: US consensus, bet365 targets, gates, analyst sweep, builder |
| `bet_slips.py` | reads bet-slip screenshots (Claude API), checks them, renders the draft for confirmation |
| `bet_slip_bot.py` | GitHub side of bet-slip issues, run by `.github/workflows/bet-slip.yml` |

## Scheduling

`.github/workflows/nfl-prop-rankings.yml` runs this every Sunday at 11:00
UTC via GitHub Actions (add `ODDS_API_KEY` as a repo secret). Since each
workflow run starts from a fresh checkout, the SQLite results log has no
durability of its own across runs -- the workflow's last step commits
`results_log.sqlite3` back to the branch after each run so the grading data
actually accumulates. If you'd rather run this locally, set up a cron job
(Mac/Linux) or Task Scheduler (Windows) to run `run_weekly.py` Sunday
morning before kickoff instead.

`.github/workflows/grade-results.yml` runs `grade_results.py` every
Tuesday at 12:00 UTC -- after Monday Night Football, so the whole week's
slate has a final score by the time it runs -- and commits the newly
graded `results_log.sqlite3` back the same way. Games it can't grade yet
(mid-week internationally-scheduled games, or a week that hasn't finished)
just stay ungraded until the following Tuesday; nothing needs to be
re-triggered by hand for that.

## Known limitations (carried into the printed output, not hidden)

- Opponent-allowed stats are grouped by broad position (WR/TE pooled into
  one group), not fine-grained matchup data (slot vs. outside, man vs.
  zone) -- same ceiling a manual version of this analysis would have.
- Name matching will have gaps at launch; expect to spend the first couple
  weeks building out `name_overrides.json` by hand.
- Rookie projections rest on a historical-analogue prior, not the player's
  own data -- always shown as `confidence="low"`.
- Tackle props may show a systematic offset if nflverse's tackle count
  disagrees with whatever source the sportsbook used to set the line -- a
  known industry data-quality issue, not a bug to chase down here.
- This is a heuristic blend, not a backtested statistical model. Grade it
  against `results_log.sqlite3` before trusting it with real money.
