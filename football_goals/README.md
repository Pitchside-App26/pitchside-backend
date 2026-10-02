# Football Goals Report

A weekly report for Saturday's league fixtures in 11 English and Scottish
leagues. It covers two markets:

- **Over 1.5 goals**: the match has 2 or more goals.
- **Goal in both halves (GIBH)**: at least one goal before half-time and at least one after.

Every percentage is calculated from this season's league results, match by
match. Nothing is copied from stats websites.

---

## Where to find the report

**Open this on your phone:** https://pitchside-app26.github.io/pitchside-backend/goals/

Bookmark it or add it to your home screen. It updates by itself every Friday
at about 6pm UK time. The same site still has the NFL page at its main
address.

At the top of the report are two tabs, **Over 1.5** and **Goal in both
halves**. Tap one to switch. Each tab has:
- its own suggested accumulator;
- its own ranked table;
- its own track record.

The report remembers which tab you used last. To bookmark a tab directly, add
`#gibh` or `#o15` to the end of the address, e.g.
https://pitchside-app26.github.io/pitchside-backend/goals/#gibh

From the report you can also open:
- **Download the CSV**: the same tables as a spreadsheet.
- **Last weekend's results**: whether each fixture landed, plus the running record.

If the page looks out of date, see "Something went wrong" below.

---

## Running it yourself

You don't have to: it runs automatically every Friday at 6pm UK time. To run
it at another time, or for a different date, use the **↻ Update now** button
at the top of the report page:

1. **First time on a phone or browser:** set up one-tap updates (about 2 minutes). Tap the **⚙︎** next to the
   button, follow the five steps shown, paste the token and tap **Save**. The token:
   - is stored only in that browser, never in the code or on the page;
   - can only start and check runs on this repo. It can't change code or read your other secrets.
2. **After that:**
   - Optionally pick a date (leave it blank for next Saturday), then tap **↻ Update now**.
   - The button shows the run's progress and reloads the page when the new report is up. It takes about a minute.

The **results page** has the same button, **↻ Check results now**. It grades
last weekend straight away instead of waiting for Sunday 7pm.

**If the button says the token was rejected:** it has expired or was pasted
wrong. Tap ⚙︎ and paste a new one.

**Without the token**, the ⚙︎ panel has a link to GitHub's Run workflow screen:
1. Tap **Run workflow**.
2. Optionally type a date.
3. Tap the green **Run workflow** button.

On a phone, use the browser rather than the GitHub app. If the button is
missing there, tap "Desktop site" in the browser menu.

---

## Changing the thresholds

All the numbers you might want to change are in one file,
[`football_goals/config.yaml`](config.yaml).

1. Open the file on GitHub and tap the **pencil** (Edit) icon.
2. Change a number. For example, set `over_1_5_highlight: 80` to `85`.
3. Tap **Commit changes**.

The next run uses the new value. The settings are:

| Setting | What it does | Default |
|---|---|---|
| `over_1_5_highlight` | Over 1.5 combined % at or above this is highlighted | 80 |
| `gibh_highlight` | GIBH combined % at or above this is highlighted | 65 |
| `min_games` | Teams with fewer league games than this are flagged | 6 |
| `accumulator:` `min_legs` / `max_legs` | Size of the Over 1.5 accumulator | 16 / 18 |
| `accumulator:` `reserves` | Reserves listed under it | 4 |
| `accumulator:` `min_combined_pct` | Lowest Over 1.5 combined % allowed in it | 80 |
| `gibh_accumulator:` `min_legs` / `max_legs` | Size of the goal-in-both-halves accumulator | 6 / 8 |
| `gibh_accumulator:` `reserves` | Reserves listed under it | 2 |
| `gibh_accumulator:` `min_combined_pct` | Lowest GIBH combined % allowed in it | 65 |
| `require_min_games` (in each) | `true` keeps flagged (low-game) teams out of that accumulator | true |
| `odds: enabled` | `true` adds an Over 1.5 price column (see Odds below) | false |
| `odds: min_price` | Only put a leg in the accumulator if its price is better than this | 1.0 (off) |
| `max_results_age_days` | Warn if a league's newest result is older than this and can't be confirmed | 9 |

Keep the spacing exactly as it is. Only change the number after the colon.

---

## How the numbers work

For each team, using this season's league games only:

- **Over 1.5 %** = games with 2+ goals ÷ games played
- **GIBH %** = games with a goal in each half ÷ games played. Second-half goals = full-time total minus half-time total.
- Home-only and away-only versions are calculated too.

For each fixture:

- **Combined %** = the average of the home team's % and the away team's %.
- **Venue-split %** = the average of the home team's **home** games and the away team's **away** games.
- **Flags**: a team with fewer than 6 games, or a league whose data checks failed.

**The accumulators** work the same way for each market:
- they take the fixtures at or above the minimum combined %, highest first;
- they leave out flagged teams and any league whose data check failed;
- with enough fixtures, they build a fold plus reserves; otherwise they say how many qualified and list them.

The two folds are different sizes:
- **Over 1.5:** 16–18 legs at 80%+.
- **Goal in both halves:** 6–8 legs at 65%+.

The GIBH fold is smaller on purpose. GIBH rates run around 60–75%, so each
extra leg costs far more than an Over 1.5 leg does. If the percentages were
exact, these would land about as often as each other:
- 8 GIBH legs at 72% each: about 7%;
- 16 Over 1.5 legs at 85% each: also about 7%.

**The track record**, on the report and the results page, shows hit rates:
- by market
- by league
- by band of combined % (below 75, 75–80, 80–85, 85–90, 90+)

Each one is compared with the **league average**: that league's season-to-date
rate at the time of the report. If a band doesn't beat its league average,
the selection isn't adding anything.

---

## Data sources, and why

| Leagues | Results with half-time scores | Fixtures and postponements | Published table used to check the data |
|---|---|---|---|
| Premier League, Championship, League One, League Two, National League | football-data.co.uk | football-data.co.uk, cross-checked with ESPN | ESPN |
| Scottish Premiership, Championship | football-data.co.uk | football-data.co.uk, cross-checked with ESPN | ESPN |
| Scottish League One, League Two | football-data.co.uk | football-data.co.uk only (ESPN doesn't cover them) | BBC Sport |
| National League North, South | LiveScore (backup: API-Football, paid) | LiveScore | BBC Sport |

- **football-data.co.uk** is free, has kept the same CSV format for over 20
  years, and includes half-time scores. In October 2026 every row in all 9 of
  these leagues had a half-time score.
- **ESPN** (free, no key) catches postponements and gives exact kick-off
  times. Its league table lets the report confirm that every club's played,
  scored and conceded figures match. That match proves no recent result is
  missing.
- **BBC Sport** (free) supplies the league table for the leagues ESPN doesn't cover.
- **LiveScore** is the only free source found that has half-time scores for
  National League North and South *and* can be reached from GitHub. It is an
  unofficial feed, so the report checks it every run:
  - it compares LiveScore's National League results with football-data.co.uk's,
    full-time and half-time, and shows the match rate in the data checks;
  - if fewer than 97% match, North/South are flagged and kept out of both accumulators;
  - North/South are also checked against BBC's table.

  Finished match days are saved in `data/livescore/`, so each day is only downloaded once.
- **API-Football** is the backup for North/South. It is used only if LiveScore
  fails, and only with a paid key: its free plan doesn't include the current season.
- **Sofascore** is not used: it blocks GitHub's servers (403).
- **SoccerSTATS** and **worldfootball.net** are not used. Both block GitHub's
  servers ("Just a moment…" Cloudflare page, error 403), so they can't be used
  automatically.

### Checks on every run

- **Right league:**
  - the club count is right (20, 24, 12 or 10);
  - every club in the published table matches a club in the results;
  - each club's games played, goals scored and goals conceded match the table.
- **Consistent:**
  - no club has played far more or fewer games than the rest;
  - no duplicate results;
  - every club in a fixture exists in that league's results.
- **Up to date:**
  - the table check above confirms it;
  - the report also shows each league's newest result date and when the source file was last updated.
- **If a league fails** to load or fails a check, a box at the **top** of the
  report says so. Its fixtures are flagged and kept out of both accumulators.
  Everything else still appears.
- **Raw downloads** from every run are kept for 30 days. They are under "Artifacts" on the run's page in the Actions tab.
- **Network failures:** each download is retried 4 times, waiting 2s, 4s, 8s and 16s.

---

## National League North and South

These come from LiveScore and need no key.

If LiveScore ever stops working, the report says so at the top and tries
API-Football instead. API-Football's free plan doesn't cover the current
season, so that backup only works with a paid plan (around $19/month). The
`API_FOOTBALL_KEY` secret is already set up; upgrading on the API-Football
website is all it would take.

---

## Odds (optional, off by default)

Prices use **The Odds API**, with the same `ODDS_API_KEY` secret as the NFL engine. Coverage checked in October 2026:

- **Priced:** Premier League, Championship, League One, League Two, Scottish Premiership.
- **Not priced:** National League, National League North/South, and Scottish Championship, League One and League Two. The report lists these as unpriced.
- Prices are only for **Over 1.5**. The goal-in-both-halves tab never shows prices.
- The 1.5 line only comes from the "alternate totals" market, which is charged
  per match. That's about 1 credit per priced fixture, so 10–40 credits a week.
- **The credits are shared with the NFL engine.** It had about 490 left this month.
- Only real quoted prices are shown (the best UK price across bookmakers). Nothing is estimated.

To turn odds on, set `odds: enabled: true` in `config.yaml`. To keep weaker
prices out of the Over 1.5 accumulator, set `min_price`; for example `1.20` only
accepts legs priced above 1.20.

---

## Something went wrong?

1. Open the **Actions** tab and tap the latest run.
2. **A green tick** means the run worked. If the page still looks old, wait a minute and refresh.
3. **A red cross** means the run failed:
   - tap the run, then the failed step, to read the log;
   - each line starts with a time and a level (`INFO`, `WARNING`, `ERROR`) and names the league it concerns.
4. A **league missing** from the report is listed in the red box at the top, with the reason.

---

## Files (for whoever maintains this)

| File | What it is |
|---|---|
| `config.yaml` | the editable settings |
| `run_report.py` | the weekly report |
| `grade_results.py` | the Sunday results run |
| `stats.py` | the calculations |
| `validate.py` | the data checks |
| `sources/` | one file per data source |
| `render.py` | HTML, CSV and Actions summary |
| `history.py` | the running record |
| `data/history.csv` | every analysed fixture and how it landed. GitHub shows it as a table. |
| `site/` | the published pages |
| `tests/` | unit tests: `python -m pytest football_goals/tests` |
