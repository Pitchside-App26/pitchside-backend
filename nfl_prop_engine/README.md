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
| `fetch_stats.py` | step 3 |
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
