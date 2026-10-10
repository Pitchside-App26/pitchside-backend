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

Bookmark it or add it to your home screen, then always open it the same way.
On an iPhone, the home-screen icon, Safari, and links opened inside other apps
each keep their own separate copy of your logged bets.

It updates by itself every Friday at about 6pm UK time. The same site still has
the NFL page at its main address.

**The accumulators lock once they're published** (from the day before the
games). Later runs, such as a delayed Friday schedule or a tap of ↻ Update now,
refresh the stats but keep the same legs and reserves in the same order, so the
list never changes under a bet you've placed. If a locked leg is postponed or
gets flagged by a data check, the card says so; swap in a reserve. To choose
afresh (only before you've bet), run the report workflow on GitHub with the
**repick** box ticked.

The page works like an app. The bar along the bottom has four sections:
- **Over 1.5** and **GIBH:** that market's suggested accumulator first, then every fixture as a one-line row. Tap a
  row for its detail, or use the **80%+ only** and **league** filters.
- **Results:** last weekend fixture by fixture, plus the running track record.
- **Info:** postponements, data sources and checks, how the numbers work, the CSV, running the report for another
  date, and the one-tap-update setup.

The page remembers the section and filters you used last. To bookmark a section, add `#o15`, `#gibh`,
`#results` or `#info` to the end of the address, e.g.
https://pitchside-app26.github.io/pitchside-backend/goals/#gibh

**Which fixtures each tab covers:**
- **Both tabs:** only 3pm (15:00 UK) kick-offs.
- **Goal in both halves:** also leaves out National League North and South, because there's no market for them.
- **What isn't affected:**
  - every fixture is still analysed and saved in the history;
  - each tab's track record counts only the fixtures that tab would have shown;
  - the summary count of fixtures analysed still includes them all.



If the page looks out of date, see "Something went wrong" below.

---

## Running it yourself

You don't have to: it runs automatically every Friday at 6pm UK time.

- **↻ (top right of the report):** updates the report for next Saturday. It shows progress at the bottom of the
  screen and reloads the page when the new report is up (about a minute).
- **Results → Check results now:** grades last weekend straight away instead of waiting for Sunday 7pm.
- **Info → Run for another date:** pick a date, then tap **Update report**.

**First time on a phone or browser:** these buttons need a one-time setup (about 2 minutes). Tapping one takes
you to **Info → One-tap updates**: follow the five steps, paste the token and tap **Save**. The token:
- is stored only in that browser, never in the code or on the page;
- can only manage this repo's workflow runs (start, check, cancel). It can't change code or read your secrets.

If a button says the token was rejected, it has expired or was pasted wrong: paste a new one in Info.

**Without the token**, the setup card links to GitHub's Run workflow screen: tap **Run workflow**, optionally type
a date, then tap the green **Run workflow**. On a phone, use the browser rather than the GitHub app; tap "Desktop
site" in the browser menu if the button is missing.

---

## The bet slip and "My bets"

Each accumulator card works as a checklist while you place the bet:

- **Tap the circle** next to a leg once it's on the bookmaker's slip. The bar under the card counts them, e.g.
  "16-fold · 12 of 16 ticked".
- **✕ (can't get this):** the leg is crossed out and the next reserve comes in. Use this when a leg is too short
  for a boost or not offered. **↺** puts it back.
- **+ on a reserve:** adds it as an extra leg, e.g. playing an 8-fold from a 6-fold. **−** takes it off again.
- **Log bet:**
  1. Pick the bookmaker. SpreadEx is pre-selected for Over 1.5 and Sky Bet for GIBH, and the last one you used
     for each market is remembered. Bet365, BetFred, BoyleSports and "Other" are in the list.
  2. Enter the stake.
  3. Enter the **return shown on the bet slip**, so boosts are included exactly.

  The bet is saved with its exact legs and appears under **Results → My bets**.

**Where your bets are kept:** only in your phone's browser. They're never uploaded, because the repo and the site
are public. Clearing browser data deletes them, so use **Info → My bets backup → Back up** now and then; the same
file moves them to another phone. **Restore** never duplicates a bet that's already there.

Coming next: settling each bet (won/lost) and profit and loss, by market and bookmaker.

To change the bookmaker list or the defaults, edit `betting:` in `config.yaml`.

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
| `markets:` `over_1_5:` `kickoffs` | UK kick-off times the Over 1.5 tab covers (`[]` = all) | `["15:00"]` |
| `markets:` `gibh:` `kickoffs` | UK kick-off times the GIBH tab covers | `["15:00"]` |
| `markets:` `gibh:` `exclude_leagues` | Leagues left off the GIBH tab | National League North, South |
| `over_1_5_highlight` | Over 1.5 combined % at or above this is highlighted | 80 |
| `gibh_highlight` | GIBH combined % at or above this is highlighted | 65 |
| `min_games` | Teams with fewer league games than this are flagged | 6 |
| `accumulator:` `min_legs` / `max_legs` | Size of the Over 1.5 accumulator | 16 / 18 |
| `accumulator:` `reserves` | Reserves listed under it | 6 |
| `accumulator:` `fill_reserves_below_line` | If fewer reserves reach 80%, top the list up with the best fixtures just under it (marked "below 80%") | true |
| `accumulator:` `note` | Reminder shown on the Over 1.5 accumulator card (`""` hides it) | the SpreadEx boost rule |
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
- with enough fixtures, they build a fold plus reserves; otherwise they say how many qualified and list them;
- reserves are in order, so swap in the top one first. If too few reach the minimum, the list is topped up with the best fixtures just under it, each marked "below 80%".

The Over 1.5 card also shows the SpreadEx boost rule: every leg must be
priced above 1/10. The report can't check SpreadEx's prices, so if a leg is
1/10 or shorter, swap it for the next reserve.

The two folds are different sizes:
- **Over 1.5:** 16–18 legs at 80%+.
- **Goal in both halves:** 6–8 legs at 65%+.

The GIBH fold is smaller on purpose. GIBH rates run around 60–75%, so each
extra leg costs far more than an Over 1.5 leg does. If the percentages were
exact, these would land about as often as each other:
- 8 GIBH legs at 72% each: about 7%;
- 16 Over 1.5 legs at 85% each: also about 7%.

**The track record**, in the Results section, shows hit rates:
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
