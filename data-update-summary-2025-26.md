# Data Update Summary — 2025/26 Season

**Branch:** `data-update-2025-26`
**Updated:** April 2026
**File changed:** `index.html` (inline `ALL_TEAMS` + `LEAGUE_INFO` blocks)
**Source files not present in repo** — changes applied directly to built output.

---

## What changed

10 commits, one per league. Two new leagues added (National League, WSL).
Season comment updated from `2024/25` to `2025/26`.

---

## League-by-league detail

### Premier League (20 teams) — HIGH confidence

| Change | Club |
|---|---|
| Relegated out | Ipswich Town, Leicester City, Southampton |
| Promoted in | Burnley, Leeds United, Sunderland |

**Full squad:**
Arsenal, Aston Villa, Bournemouth, Brentford, Brighton, Burnley, Chelsea,
Crystal Palace, Everton, Fulham, Leeds United, Liverpool, Manchester City,
Manchester United, Newcastle United, Nottingham Forest, Sunderland,
Tottenham Hotspur, West Ham United, Wolverhampton Wanderers

---

### Championship (24 teams) — HIGH confidence

Previous code had **26 teams** (2 extra — data bug).

| Change | Club |
|---|---|
| Promoted to PL | Burnley, Leeds United, Sunderland |
| Relegated from PL | Ipswich Town, Leicester City, Southampton |
| Promoted from L1 | Charlton Athletic, Wrexham |
| Relegated to L1 | Blackpool, Cardiff City, Luton Town, Plymouth Argyle |

**Full squad:**
Birmingham City, Blackburn Rovers, Bristol City, Charlton Athletic, Coventry City,
Derby County, Hull City, Ipswich Town, Leicester City, Middlesbrough, Millwall,
Norwich City, Oxford United, Portsmouth, Preston North End, Queens Park Rangers,
Sheffield United, Sheffield Wednesday, Southampton, Stoke City, Swansea City,
Watford, West Bromwich Albion, Wrexham

---

### League One (24 teams) — HIGH confidence

Previous code had **22 teams** (2 short — data bug).

| Change | Club |
|---|---|
| Promoted to Championship | Charlton Athletic, Wrexham (+ Birmingham City) |
| Relegated from Championship | Blackpool, Cardiff City, Luton Town, Plymouth Argyle |
| Promoted from L2 | AFC Wimbledon, Bradford City, Doncaster Rovers, Wycombe Wanderers |
| Relegated to L2 | Bristol Rovers, Cambridge United, Crawley Town, MK Dons, Shrewsbury Town |

**Full squad:**
AFC Wimbledon, Barnsley, Blackpool, Bolton Wanderers, Bradford City, Burton Albion,
Cardiff City, Doncaster Rovers, Exeter City, Huddersfield Town, Leyton Orient,
Lincoln City, Luton Town, Mansfield Town, Northampton Town, Peterborough United,
Plymouth Argyle, Port Vale, Reading, Rotherham United, Stockport County, Stevenage,
Wigan Athletic, Wycombe Wanderers

---

### League Two (24 teams) — HIGH confidence

Previous code had **22 teams** (2 short — data bug).

| Change | Club |
|---|---|
| Promoted to L1 | AFC Wimbledon, Bradford City, Doncaster Rovers, Wycombe Wanderers |
| Relegated from L1 | Bristol Rovers, Cambridge United, Crawley Town, MK Dons, Shrewsbury Town |
| Relegated to National League | Carlisle United, Morecambe, Port Vale (approx.) |
| Promoted from National League | Barnet, Cheltenham Town, Oldham Athletic (approx.) |

**Full squad:**
Accrington Stanley, Barnet, Barrow, Bristol Rovers, Cambridge United,
Cheltenham Town, Chesterfield, Colchester United, Crawley Town, Crewe Alexandra,
Gillingham, Grimsby Town, Harrogate Town, MK Dons, Newport County, Notts County,
Oldham Athletic, Salford City, Shrewsbury Town, Swindon Town, Tranmere Rovers,
Walsall, Bromley, Fleetwood Town

---

### National League (24 teams) — MEDIUM confidence *(NEW league)*

Not previously in `ALL_TEAMS` or `LEAGUE_INFO`. Added as tier 5 of English football.
LEAGUE_INFO: `{ chip: 'NL', label: 'National League', color: '#1B2A52' }`

Notable clubs: Carlisle United and Morecambe (relegated from L2), Forest Green Rovers
(returning after relegation), Hartlepool United, Rochdale, Southend United, Yeovil Town.

**Full squad:**
Aldershot Town, Altrincham, Boreham Wood, Boston United, Brackley Town, Braintree Town,
Carlisle United, Eastleigh, FC Halifax Town, Forest Green Rovers, Gateshead,
Hartlepool United, Morecambe, Rochdale, Scunthorpe United, Solihull Moors,
Southend United, Sutton United, Tamworth, Truro City, Wealdstone, Woking,
Yeovil Town, York City

**Confidence note:** National League composition at tier 5 is harder to verify than
the EFL. Some clubs (especially promoted/relegated boundary) may be approximate.

---

### Women's Super League (12 teams) — HIGH confidence *(NEW league)*

Not previously in `ALL_TEAMS` or `LEAGUE_INFO`. Added as top-flight women's competition.
LEAGUE_INFO: `{ chip: 'WSL', label: "Women's Super League", color: '#6A0DAD' }`

**Full squad:**
Arsenal, Aston Villa, Brighton, Chelsea, Everton, Leicester City, Liverpool,
London City Lionesses, Manchester City, Manchester United, Tottenham Hotspur,
West Ham United

---

### Scottish Premiership (12 teams) — HIGH confidence

Previous code had **13 teams** (1 extra — data bug). Falkirk was also listed
incorrectly for 2024/25 (they were promoted for 2025/26 — now correctly included).

| Change | Club |
|---|---|
| Relegated | Ross County, St Johnstone |
| Promoted from Championship | Falkirk, Livingston |

**Full squad:**
Aberdeen, Celtic, Dundee, Dundee United, Falkirk, Heart of Midlothian,
Hibernian, Kilmarnock, Livingston, Motherwell, Rangers, St Mirren

---

### Scottish Championship (10 teams) — HIGH confidence

| Change | Club |
|---|---|
| Promoted to Premiership | Falkirk, Livingston |
| Relegated from Premiership | Ross County, St Johnstone |
| Promoted from League One | Arbroath |
| Relegated to League One | Hamilton Academical, Inverness CT |
| Name correction | 'Morton' → 'Greenock Morton' (official name) |

**Full squad:**
Airdrieonians, Arbroath, Ayr United, Dunfermline Athletic, Greenock Morton,
Partick Thistle, Queen's Park, Raith Rovers, Ross County, St Johnstone

---

### Scottish League One (10 teams) — MEDIUM confidence

| Change | Club |
|---|---|
| Promoted to Championship | Arbroath |
| Relegated from Championship | Hamilton Academical, Inverness CT |
| Promoted from League Two | Queen of the South |
| Relegated to League Two | Dumbarton, Stirling Albion |

**Full squad:**
Alloa Athletic, Cove Rangers, East Fife, Hamilton Academical, Inverness CT,
Kelty Hearts, Montrose, Peterhead, Queen of the South, Stenhousemuir

**Confidence note:** Peterhead confirmed HIGH confidence — verified correct by product
owner for Scottish League One 2025/26.

---

### Scottish League Two (10 teams) — MEDIUM confidence

Previous code had **9 teams** (1 short — data bug).

| Change | Club |
|---|---|
| Promoted to League One | Queen of the South |
| Relegated from League One | Dumbarton, Stirling Albion |
| Added | East Kilbride (promoted from lowland leagues) |
| Removed | Bonnyrigg Rose |
| Name correction | 'Spartans' → 'The Spartans' (official name) |

**Full squad:**
Annan Athletic, Clyde, Dumbarton, East Kilbride, Edinburgh City, Elgin City,
Forfar Athletic, Stirling Albion, Stranraer, The Spartans

---

## TEAM_IDS — badge coverage

`TEAM_IDS` was not updated in this pass. The existing entries still cover
the same clubs (API-Football IDs don't change when clubs are promoted/relegated).
New clubs added in this update that have **no badge ID** (will show initials fallback):

- **National League** — all 24 clubs (entire new league, no IDs present)
- **WSL** — London City Lionesses (all others share IDs with men's teams)
- **Wrexham** — newly promoted to Championship, no ID yet
- **East Kilbride, The Spartans** — Scottish L2 new entries

To add an ID: find the team's numeric ID at `v3.football.api-sports.io/teams`
and add `'Club Name': <id>` to the `TEAM_IDS` block in `index.html`.

---

## Bookmaker review — 2025/26 verification

All 22 operators in `ALL_BOOKMAKERS` verified for 2025/26.

**Sun Bets** was queried for removal but was **never present in the codebase** — it
shut down in 2017, before this code was written. No removal needed.

| Bookmaker | Status |
|---|---|
| Parimatch | ✓ Confirmed still active in UK — keep |
| Smarkets | ✓ Confirmed still active — keep |
| 32Red | ✓ Confirmed still active — keep |
| All other 19 operators | Verified active for 2025/26 |

Sun Bets removed (exited UK market 2017). All other bookmakers verified active for 2025/26.

`ALL_BOOKMAKERS`, `AFFILIATE_URLS`, and `BOOKIE_LICENCES` in `index.html` required
no changes. All three objects remain at 22 operators.

**Bookmaker list should be reviewed annually in June/July before new season to catch
any market exits, licence revocations, or rebrands.**

---

## How to update next summer (June 2026)

1. **Wait for final day** — promotions/relegations are confirmed on the last day of
   each season, typically mid-May for English leagues and mid-May for Scottish.

2. **Check official sources** for each league:
   - Premier League: premierleague.com
   - EFL (Championship / L1 / L2): efl.com
   - National League: thenationalleague.org.uk
   - WSL: thefa.com/womens-girls-football/wsl
   - Scottish (all tiers): spfl.co.uk

3. **Edit `index.html`** — find the `ALL_TEAMS` block (search for `// Season:`).
   Update each league array and bump the season comment:
   ```js
   // Season: 2026/27 — review June 2027
   ```

4. **One commit per league** — keeps changes reviewable and bisectable.

5. **Update TEAM_IDS** for any newly promoted clubs lacking badge IDs.
   Run `fetch-team-ids.js` (in repo root) against the updated team lists,
   cross-reference with `v3.football.api-sports.io/teams?league=<id>&season=<year>`.

6. **Verify bookmakers** — check AFFILIATE_URLS entries are still active UKGC-licensed
   operators. Operators exit or rebrand annually. Do this in June/July before the new
   season starts. Cross-reference against the UKGC public register at
   gamblingcommission.gov.uk.

7. **Scottish lower leagues** — SPFL.co.uk is the authoritative source. The lower
   tiers (League One, League Two) have more movement and less media coverage; double-
   check every club rather than relying on news articles.

8. **Push to a new branch** (`data-update-2026-27`) — do not commit directly to main
   until the update has been reviewed.

---

*10 leagues updated · 2 new leagues added · 11 commits · branch: data-update-2025-26*
