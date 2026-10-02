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

From the report you can also open:
- **Download the CSV**: the same tables as a spreadsheet.
- **Last weekend's results**: whether each fixture landed, plus the running record.

If the page looks out of date, see "Something went wrong" below.

---

## Running it yourself

You don't have to. It runs automatically every Friday at 6pm (UK time). To run
it at another time, or for a different date:

1. Go to https://github.com/Pitchside-App26/pitchside-backend/actions. On a
   phone, use the browser rather than the GitHub app. If the button is
   missing, tap "Desktop site" in the browser menu.
2. In the left-hand list, tap **Football Goals Report (weekly)**.
3. Tap **Run workflow**.
4. Optionally type a date like `2026-10-10`. Leave it blank for next Saturday.
5. Tap the green **Run workflow** button.

It takes about a minute. When the run shows a green tick, refresh the report page.

The **Football Goals Results (weekly)** workflow runs by itself on Sunday at
7pm. It runs again on Monday at 1pm to catch any late results. It has the
same Run workflow button if you ever want to run it by hand.

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
| `min_legs` / `max_legs` | Size of the suggested accumulator | 16 / 18 |
| `reserves` | Reserves listed under the accumulator | 4 |
| `min_combined_pct` | Lowest Over 1.5 combined % allowed in the accumulator | 80 |
| `require_min_games` | `true` keeps flagged (low-game) teams out of the accumulator | true |
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

**The accumulator** takes Over 1.5 fixtures with a combined % of 80 or more,
highest first. It leaves out flagged teams and any league whose data check
failed. With enough fixtures it builds a 16–18 fold plus 3–4 reserves.
Otherwise it tells you how many qualified and lists them.

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
| National League North, South | API-Football (needs a key) | API-Football | BBC Sport |

- **football-data.co.uk** is free, has kept the same CSV format for over 20
  years, and includes half-time scores. In October 2026 every row in all 9 of
  these leagues had a half-time score.
- **ESPN** (free, no key) catches postponements and gives exact kick-off
  times. Its league table lets the report confirm that every club's played,
  scored and conceded figures match. That match proves no recent result is
  missing.
- **BBC Sport** (free) supplies the league table for the leagues ESPN doesn't cover.
- **API-Football** is the only source found that has half-time scores for
  National League North and South *and* can be reached from GitHub. It needs a
  key (see below).
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
  report says so. Its fixtures are flagged and kept out of the accumulator.
  Everything else still appears.
- **Raw downloads** from every run are kept for 30 days. They are under "Artifacts" on the run's page in the Actions tab.
- **Network failures:** each download is retried 4 times, waiting 2s, 4s, 8s and 16s.

---

## National League North and South (needs a free key)

These two leagues stay off the report until there is an `API_FOOTBALL_KEY` secret.

1. Sign up at https://dashboard.api-football.com/register. It's free and gives 100 requests a day; each run uses about 5.
2. Copy your API key from the dashboard.
3. On GitHub, open the repo's **Settings → Secrets and variables → Actions → New repository secret**.
4. Set the name to `API_FOOTBALL_KEY` and paste the key as the value. Save.

The next run picks it up.

**If the free plan doesn't cover the current season**, the report will say so
at the top. API-Football's free plan has limited which seasons it serves in
the past. You would then need the cheapest paid plan, around $19/month. Check
the price on their pricing page before paying.

Keys only ever live in GitHub secrets, never in the code.

---

## Odds (optional, off by default)

Prices use **The Odds API**, with the same `ODDS_API_KEY` secret as the NFL engine. Coverage checked in October 2026:

- **Priced:** Premier League, Championship, League One, League Two, Scottish Premiership.
- **Not priced:** National League, National League North/South, and Scottish Championship, League One and League Two. The report lists these as unpriced.
- The 1.5 line only comes from the "alternate totals" market, which is charged
  per match. That's about 1 credit per priced fixture, so 10–40 credits a week.
- **The credits are shared with the NFL engine.** It had about 490 left this month.
- Only real quoted prices are shown (the best UK price across bookmakers). Nothing is estimated.

To turn odds on, set `odds: enabled: true` in `config.yaml`. To keep weaker
prices out of the accumulator, set `min_price`; for example `1.20` only
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
