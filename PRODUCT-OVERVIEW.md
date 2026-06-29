# Pitchside — "The Rundown" · Full Product Overview
*Document date: 2026-05-08. Load this into Claude to give it full context of what this app is.*

---

## 1. What Is This App?

**Pitchside — The Rundown** is a mobile-first football companion app aimed at UK football fans. It sits at the intersection of three things no single app currently does well together:

1. **Live match data** — scores, timelines, lineups, tables
2. **Match day logistics** — pubs, transport, tickets, food near the ground
3. **Responsible betting intelligence** — AI-generated bets, odds comparison across all major UK bookmakers, live bet tracking

The core proposition: you open the app before kick-off and it tells you everything you need for your day — from which pubs are home-only to where the best odds are to what Arsenal's xG is.

The app is **pre-launch**. All screens exist as a working high-fidelity prototype. The data layer (Supabase + API-Football) is partially wired up. The priority is completing the data pipeline and then launching.

---

## 2. Brand & Design Language

**Name:** Pitchside (brand) / The Rundown (product name, shown in-app)

**Wordmark:** `Pitch_side_` rendered as `Pitch<em>side</em>` — the "side" is always italic. Similarly `The Run<em>down</em>`.

**Colour palette (existing — light/warm):**
- `--parchment` `#F5F0E8` — main background, warm off-white
- `--card` `#FDFBF7` — card/surface near-white
- `--ink` `#1A1714` — primary text, near-black with warmth (225 uses — the most-used token)
- `--ink3` `#6B6560` — secondary text / metadata
- `--ink4` `#A09890` — muted text, labels, captions
- `--live` `#B02A18` — brand red. Live badges, active accents, scores, wordmark
- `--forest` `#1A5C38` — brand green. Wins, positive states, BTTS, away-friendly pubs
- `--gold` `#8B6914` — brand amber. Draws, warnings, building crowd
- `--rule` `rgba(26,23,20,0.09)` — dividers, row separators
- `--ucl` `#003087` — UCL blue

**v1.0 design tokens (dark mode — added to codebase, not yet applied to components):**
A second set of 62 semantic tokens (`--bg-primary`, `--text-primary`, `--brand-red`, `--space-*`, `--radius-*` etc.) has been defined in `design-tokens.css` and injected into `index.html`. These form the foundation for a future dark mode or full design refresh. No components use them yet — the app still runs entirely on the warm/light palette above.

**Typography:**
- `--fd` / `Playfair Display` — display/decorative. Wordmark, hero scores, screen headers
- `--fs` / `Instrument Sans` — body text workhorse
- `--fm` / `IBM Plex Mono` — scores, odds, times, badges, labels (137 uses — the most distinctive typographic choice)

**Design feel:** Editorial, warm, newspaper-meets-sports-ticker. Inspired by The Athletic's editorial aesthetic. Not the neon/dark aesthetic of Bet365 or Sky Bet.

---

## 3. App Architecture

**Single-file frontend:** The entire frontend is `index.html` — one 243 KB file containing all HTML, CSS (inline `<style>` tags), and JavaScript. This file is the committed built output. The product owner builds it locally using `build.py` which stitches together these source files (not in the repo):
- `rundown-base.html` — HTML shell
- `phase-a-styles.css` + `phase-a-screens.html` + `phase-a-additions.js` + `phase-a-additions-2.js` — core app, auth, onboarding
- `nav-1-styles.css` + `nav-1-scripts.js` — bottom navigation bar
- `phase-b-styles.css` + `phase-b-scripts.js` — betting features, offers, odds comparison

**Backend:** Vercel serverless function at `/api/sync.js` — pulls fixture data from API-Football and upserts to Supabase.

**Database:** Supabase (PostgreSQL). Tables include `matches`, `profiles`. Auth via Supabase email/password.

**Deployment:** Vercel (Hobby tier). Cron runs `/api/sync` at 06:00 and 12:00 UTC daily.

**Navigation:** A bottom nav bar (`rundown-nav`) with 5 tabs — Home, Matches, Match Day, Bets, Profile. Implemented in Phase NAV-1. There are also dot indicators at the bottom of the phone shell for direct screen navigation (prototype mode).

---

## 4. The Screen Map (All 14 Screens)

The app has 14 named screens organised into 4 sections. All are implemented as high-fidelity prototypes.

### Section 1 — Fixtures (screens n0–n4)

**n0 · Today / Live Scores (Home screen)**
The default landing screen. Contains:
- A 7-day date strip (Mon–Sun, current day selected)
- A hero match card — the most prominent live/upcoming fixture, shown full-width with team crests, score, live minute indicator, and a graphical pitch background
- A scrollable fixture list grouped by competition (e.g. Premier League, then UCL), showing each match as a row with time/minute, team names, score, live indicator
- A live counter badge in the header ("3 LIVE")
- A notification bell icon

**n1 · Match Detail — Timeline**
Drills into a specific match. Contains:
- A sticky match header (both teams, score, live minute)
- A tab strip: Timeline / Stats / Lineups / H2H / Match Day / Bet
- A timeline of events (goals with scorer + assist, yellow/red cards, substitutions) in chronological order, each showing the running score
- A live polling status indicator at the bottom showing the refresh interval ("Active Polling · 15s intervals") with a note that goal alerts trigger 5-second polling for 2 minutes ("Red Alert")

**n2 · Match Detail — Lineups**
- Same sticky match header
- Same tab strip (Lineups tab active)
- A formation pitch graphic showing both XIs on a top-down pitch view with player numbers and abbreviated surnames, colour-coded by team
- Both formations labelled (e.g. Arsenal · 4–3–3, Chelsea · 4–2–3–1)
- GK differentiated from outfield players

**n3 · Player Stats**
- Player hero section: avatar initials, name, club, position, nationality, squad number, season rating
- Tab strip: Season / This Match / Form
- A "bet context" banner — if the user has a bet on this player (e.g. Anytime Goalscorer), a yellow banner highlights it with live stat updates (shots count etc.)
- A season stats grid: Goals, Assists, Apps, Shots/90, Key passes, xG/90, Pass accuracy, Dribbles, Average rating
- A "Last 5 Appearances" form section — each game shows result (W/D/L pill), opposition, key stats (goals, assists, shots), and a colour-coded match rating

**n4 · Tables — Premier League**
- Live league standings
- UCL/relegation zone colour-banding
- 5-game form pills per team
*(Static prototype — dynamic data not yet wired)*

---

### Section 2 — Match Day Hub (screens n5–n8)

All four Match Day screens share:
- A sticky match header showing the current live match
- A tab strip: Timeline / Stats / Lineups / H2H / Match Day / Bet
- A sub-strip for the Match Day section: 🚇 Transport / 🍷 Pubs / 🍔 Food / 🎟 Tickets

**n5 · Match Day Hub — Pubs**
The fan-sourced pub intelligence screen. Shows pubs near the ground with:
- Fan-reported status: Home Only / Mixed / Away Friendly
- Crowd level: Quiet / Building / Packed
- A "Fan Verified 🔴" badge when a report has 3+ upvotes
- Distance in minutes walking and metres
- Google rating and review count
- A flag button to report inaccurate info
- Report pills showing things like "Away fans not allowed · reported 30m ago"
- A "Your Trust Level" card at the bottom — showing the user's tier (Regular Fan / Trusted Fan / Legend), report count, and trust score

**n6 · Match Day Hub — Tickets**
Last-minute ticket resale. Shows:
- A hero banner: "Last Minute Entry — Arsenal vs Chelsea · Available Now"
- Individual seat listings from StubHub, Viagogo, Seat Wave — each showing section, row, seats available, price
- Commission disclosure footer
- 18+ disclaimer

**n7 · Match Day Hub — Transport**
Fan-reported transport disruptions + TfL-style info:
- An alert card at the top for any active disruptions (e.g. "Piccadilly Line Delays · Reported by 3 fans")
- Transport options grouped by type: By Tube / By Rail / By Bus
- Each option shows: icon, station/route name, line, walking distance, current status (Good Service / Delays), next train time, crowd build-up level

**n8 · Match Day Hub — Food**
Top food picks within 500m, sorted by fan rating:
- Each result shows: emoji for cuisine type, name, Google rating, distance, price tier (£/££/£££), estimated wait time, cuisine category

---

### Section 3 — Betting (screens n9–n12)

**n9 · AI Bet Generator**
The standout feature. An AI-generated bet recommendation engine:
- Controls: bet type (Accumulator / Treble / Double / Single), data window (Last 5 matches / Full season)
- Shows number of fixtures analysed ("14 matches analysed")
- Outputs a suggestion card with combined odds and potential return
- Each leg shows: match, selection (e.g. "Arsenal to Win"), stat-based reasoning paragraph, fractional odds, a confidence bar (percentage fill)
- CTA: "Add to Bet Slip ↗" and "Regenerate"
- Responsible gambling links (BeGambleAware, GamStop, helpline number) at the bottom of every betting screen

**n10 · Bet Builder — Odds Comparison**
The bet slip combined with multi-bookmaker odds comparison:
- A dark-header bet slip showing the accumulated legs with match, selection, market, and odds for each leg
- Leg removal (✕ button)
- A stake input with quick-select buttons (£2 / £5 / £10 / £25 / £50)
- A summary: combined odds, stake, potential return
- Market tabs: Result / BTTS / Over 2.5 / Handicap
- An odds comparison table headed "Compare Odds · Best Price First" — populated by `renderOddsComparison()` which ranks all user-enabled bookmakers from best to worst odds for the selected market
- Bookmakers the user has toggled as "I have an account" are highlighted with a "✓ You have an account" indicator
- "Prices update every 30 seconds"

**n11 · In-Play Bet Tracker**
Live tracking of the user's active bets:
- A tracker hero card showing the overall accumulator status: running odds, potential return if all land, progress bar (legs complete / total legs)
- Per-leg status: ✅ Won / ⏱ In progress (with live score update) / ⏳ Not started
- A stats strip: Win rate / All time P&L / Total bets placed / Best winning streak
- A "Recent History" section showing past bets (date, type, result, P&L)

**n12 · Affiliate Offers — UKGC**
The monetisation screen. Betting offers from UKGC-licensed bookmakers:
- A featured offer hero card (dynamically populated by `loadOffers()`)
- Filter tabs: All / Welcome / Free Bets / Cashback
- Offer cards dynamically rendered by `renderOfferCards()` from Supabase (with `OFFERS_FALLBACK` as static fallback)
- UKGC compliance footer on every offer: 18+ / BeGambleAware / GamStop / Helpline
- A UKGC Licensed indicator in the nav bar

---

### Section 4 — Profile (screen n13)

**n13 · User Profile**
The account and personalisation hub:
- A hero section: avatar (initials), trust tier badge ("TRUSTED FAN"), display name, member since date, reports count
- Profile tabs: Overview / Bets / Reports / Settings
- Stat strip: Win rate / P&L / Total bets / Fan reports submitted
- **Favourite Teams** — the teams selected during onboarding, shown as rows (team name + league). Tappable.
- **My Bookmaker Accounts** — toggle list of 22 bookmakers. Toggled-on bookmakers appear highlighted in the odds comparison. Accompanied by a note: "Toggle on to see ✓ You have an account in odds comparison"
- **Responsible Gambling** tools:
  - Deposit limit reminder (Off/On)
  - Session time alert (configurable, shown as "30 min")
  - "Take a break" option
  - Embedded BeGambleAware / GamStop / helpline footer

---

### Auth Screens (overlaid, not in the main SCREENS array)

**auth-login:** Standard sign-in form (email + password). Link to register. Error display. Supabase-not-connected warning (shown if Supabase is unavailable).

**auth-register:** Full registration form (first name, last name, email, password × 2, GDPR/18+ consent checkbox). "Free forever. Takes 60 seconds."

**Onboarding — 3 steps (shown after registration):**

**auth-onboard1a · My Club (Step 1 of 3, mandatory)**
A two-panel layout:
- Left 35%: league selector list (all UK leagues)
- Right 65%: team list for selected league, with search input
- User selects their primary supported club (required, 1 only)
- Continue button disabled until a club is selected

**auth-onboard1b · Add Teams (Step 2 of 3)**
Same two-panel layout, with two tabs:
- **Watch Live** (≤5 teams) — teams attended in person. Drives Match Day Hub (pubs, transport, tickets for their fixtures)
- **Follow Scores** (≤10 teams) — teams to follow on the live screen
- Skip dialog ("Without teams, your home screen will show all UK football fixtures instead of a personalised feed")

**auth-onboard2 · Bookmaker Accounts (Step 3 of 3)**
A scrollable toggle list of all 22 bookmakers. Optional. Updates odds comparison immediately.

**Age gate:** A full-screen overlay shown before everything else. Confirms the user is 18+. Required before any content is accessible.

---

## 5. The Leagues & Teams

Updated to **2025/26 season** (review June 2026). Full lists are in `data-update-summary-2025-26.md`.

| League | Teams | API-Football ID | Notes |
|---|---|---|---|
| Premier League | 20 | 39 | Synced |
| Championship | 24 | 40 | Synced |
| League One | 24 | 41 | Synced |
| League Two | 24 | 42 | Synced |
| National League | 24 | 48 | **NOT in sync.js LEAGUES array** |
| Women's Super League | 12 | 736 | **NOT in sync.js LEAGUES array** |
| Scottish Premiership | 12 | 179 | Synced |
| Scottish Championship | 10 | — | **NOT in sync.js LEAGUES array** |
| Scottish League One | 10 | — | **NOT in sync.js LEAGUES array** |
| Scottish League Two | 10 | — | **NOT in sync.js LEAGUES array** |

Additionally synced but not in the team picker: La Liga (140), Serie A (135), Bundesliga (78), Ligue 1 (61), Primeira Liga (94), Eredivisie (88), Süper Lig (203), Saudi Pro League (307), MLS (253), Brasileirão (71), UCL (2), UEL (3), UECL (848).

---

## 6. The Bookmakers (22 total)

Verified by product owner in May 2026. All UKGC licensed.

Bet365, Sky Bet, Paddy Power, William Hill, Ladbrokes, Coral, Betfair, Unibet, 888Sport, BetVictor, BoyleSports, Betway, bet-at-home, Betfred, Spreadex, Sporting Index, Smarkets, Matchbook, LiveScore Bet, Betano, Bwin, Betsson.

These power: the Bookmaker Accounts toggle in onboarding and profile; the Odds Comparison ranking in Bet Builder; the Affiliate Offers screen.

**Architecture:** A single `BOOKMAKERS` master array (consolidated in batch-3) drives `ALL_BOOKMAKERS`, `AFFILIATE_URLS`, and `BOOKIE_LICENCES`. Adding a bookmaker requires editing only the master array.

---

## 7. Key Features & Differentiators

### 7.1 — The Trust System (Fan Reports)
The Match Day Hub's pub, transport, and food data is fan-sourced. Users submit reports; reports from verified users carry more weight. The trust system works as follows:
- Users accumulate a **trust score** based on report accuracy
- **Tiers:** Regular Fan → Trusted Fan → Legend (names TBC, example in prototype)
- "Fan Verified 🔴" badge appears when a pub status has 3+ independent upvotes from trusted fans
- Users can flag inaccurate reports
- Trust level is displayed on the profile screen

This is the community network effect that makes the Match Day Hub defensible. Other apps show static data; Pitchside shows what fans are reporting right now.

### 7.2 — Adaptive Live Polling
The match timeline doesn't just poll at a fixed interval. The system uses:
- **Normal mode:** 15-second polling intervals
- **Red Alert mode:** Triggered when a goal is scored — drops to 5-second intervals for 2 minutes to capture any immediate VAR reversal, second goal, or correction
This is visible to users via a "polling bar" on the timeline screen.

### 7.3 — AI Bet Generator
A betting recommendation engine that analyses today's fixtures (configurable: Last 5 matches / Full season data) and generates suggested accumulators with per-leg reasoning. Each leg has:
- The selection (e.g. "Arsenal to Win", "Over 2.5 Goals", "Both Teams to Score", "Draw No Bet")
- A 2-3 sentence stat-based justification
- Fractional odds and a confidence bar
- A suggested stake and potential return

The AI generator is NOT generic — it references real stats and real match history. It is designed to feel like a knowledgeable friend's recommendation, not a slot machine.

### 7.4 — Cross-Bookmaker Odds Comparison
The Bet Builder shows odds for the selected market across all 22 bookmakers ranked best to worst. Bookmakers the user has toggled on in their profile are highlighted with "✓ You have an account" — so the user can see their best available price among bookmakers they're actually registered with. Prices update every 30 seconds.

### 7.5 — In-Play Bet Tracker
After placing a bet, users can track it live. The tracker shows:
- Which legs have landed (✅), are in progress (⏱ with live score), or haven't started (⏳)
- Running odds as legs land
- Potential return updated in real time
- Historical P&L and win rate stats

### 7.6 — Personalised Fixture Feed
Onboarding captures the user's supported clubs and leagues. The home screen surfaces their teams first rather than showing a generic national fixture list. The Watch Live vs Follow Scores distinction means Match Day Hub features (pubs, transport, tickets) only appear for teams the user physically attends.

### 7.7 — Compliance-First Betting UX
Every betting screen carries UKGC-mandated responsible gambling information:
- 18+ label
- BeGambleAware.org link
- GamStop.co.uk link
- National helpline: 0808 802 0133
- "Not financial advice" / "Data-driven analysis only" disclaimers on AI screens
- All bookmakers listed are UKGC licensed; this is surfaced explicitly in the offers screen
- A dedicated Responsible Gambling section in the user profile (deposit limit reminders, session time alerts, take a break)

---

## 8. Data Pipeline

### How Fixtures Get Into the App

1. `api/sync.js` runs on Vercel at 06:00 and 12:00 UTC
2. It calls `GET https://v3.football.api-sports.io/fixtures` with `date: today` and `season: 2025` for each of 18 league IDs
3. Results are upserted into the Supabase `matches` table with `onConflict: 'id'`
4. The app reads from Supabase to display live scores

### Known Problems with the Current Sync (Under Investigation)

The `sync-investigation` branch has diagnostic logging deployed. We are actively trying to confirm which of the following problems apply:

1. **Today-only window:** The function only requests today's fixtures. On non-match days it does nothing but look healthy. Future fixtures (tomorrow, this weekend) never appear.
2. **No lookback:** Yesterday's final scores are never updated after midnight.
3. **Missing leagues:** National League, WSL, Scottish Championship/L1/L2 are in the team picker but not in the sync LEAGUES array — their fixtures are never fetched.
4. **API key status unknown:** It has not been confirmed whether `FOOTBALL_API_KEY` is set in Vercel environment variables. If not, every call fails silently.
5. **Always returns HTTP 200:** Even if all 18 leagues fail, the function returns `{ total_matches_synced: 0, errors: [] }` which looks like a clean run.
6. **No staleness detection:** Every run upserts all fixtures regardless of whether anything changed.

### Planned Sync Rewrite (Once Investigation is Complete)
- Change `date: today` to a window: yesterday through 7 days ahead (using `from`/`to` params)
- Add the 5 missing leagues
- Parallelise the 18 league calls with `Promise.all()` to avoid Vercel timeout
- Return HTTP 500 when all leagues error
- Remove investigation logging

---

## 9. Authentication Flow

1. App loads → Age gate shown (confirm 18+)
2. Age gate confirmed → Auth screen shown (login or register)
3. Login: `doLogin()` → Supabase `signInWithPassword()` → on success, `checkAuthState()` sets `authUser` → profile screen updates
4. Register: `doRegister()` → Supabase `signUp()` → on success, redirects to onboarding step 1
5. Onboarding: 3 steps (My Club → Add Teams → Bookmakers) → `saveAllOnboardingData()` writes to Supabase `profiles` table → user lands on home screen
6. On every app load: `initSupabase()` → `checkAuthState()` → `getSession()` — the `_authChecking` flag prevents the logged-out state from flashing before the session resolves

### Known Issue — `updateProfileScreen()` Always No-ops
The function that dynamically populates the profile screen targets `getElementById('profile-dynamic')` — an element that doesn't exist in the HTML. It has a `if (!container) return;` guard so it silently does nothing. The profile screen always shows static prototype content ("James D.", Arsenal/Liverpool). **This needs to be fixed before launch.** Fix: wrap the profile scroll content in `<div id="profile-dynamic">`.

---

## 10. Monetisation

Three revenue streams are built into the prototype:

1. **Affiliate commissions on betting offers** — The Offers screen (n12) shows UKGC-licensed bookmaker sign-up and reload offers. Pitchside earns a CPA or revenue share when users click through and register/deposit.
2. **Ticket resale commission** — The Tickets screen (n6) links to StubHub, Viagogo, and Seat Wave. A commission disclosure is shown: "Pitchside earns a commission on ticket sales."
3. **Future:** In-app premium tier (speculated — not in prototype). The fan trust system could have premium tiers. The AI Bet Generator could be gated.

---

## 11. What Is Built vs What Is Wired

| Feature | Prototype | Live Data |
|---|---|---|
| Today screen fixture list | ✅ Full UI | ⚠️ Partially (sync issues) |
| Match Detail — Timeline | ✅ Full UI | ❌ Not wired |
| Match Detail — Lineups | ✅ Full UI | ❌ Not wired |
| Player Stats | ✅ Full UI | ❌ Not wired |
| League Tables | ✅ Full UI | ❌ Not wired |
| Match Day Hub — Pubs | ✅ Full UI | ❌ Not wired (no pub data source) |
| Match Day Hub — Tickets | ✅ Full UI | ❌ Not wired (no StubHub/Viagogo API) |
| Match Day Hub — Transport | ✅ Full UI | ❌ Not wired (no TfL API) |
| Match Day Hub — Food | ✅ Full UI | ❌ Not wired (no Google Places API) |
| AI Bet Generator | ✅ Full UI | ❌ Not wired (no AI backend) |
| Odds Comparison | ✅ Full UI | ⚠️ Partially (OFFERS_FALLBACK static data) |
| In-Play Bet Tracker | ✅ Full UI | ❌ Not wired |
| Affiliate Offers | ✅ Full UI | ⚠️ OFFERS_FALLBACK until Supabase live |
| Auth (login / register) | ✅ Wired | ✅ Supabase live |
| Onboarding (3 steps) | ✅ Wired | ✅ Saves to Supabase |
| User Profile | ⚠️ Static prototype shown | ❌ Dynamic update broken (see §9) |

---

## 12. Outstanding Actions (Priority Order)

### Immediate / Blocking

1. **Complete sync investigation** — Deploy `sync-investigation` branch preview to Vercel, trigger `/api/sync`, paste Vercel function logs back to Claude. This tells us whether `FOOTBALL_API_KEY` is set, whether data flows, and what exactly is broken. Branch is already pushed.

2. **Fix profile screen `#profile-dynamic`** — Add `<div id="profile-dynamic">` wrapper around the scrollable body of screen `#n13`. This makes `updateProfileScreen()` actually execute, replacing the "James D." prototype with real auth data. Without this, logged-in users always see fake prototype content.

### High Priority

3. **Rewrite `api/sync.js`** — Once investigation is done. Changes:
   - Date window: yesterday through next 7 days (not just today)
   - Add missing leagues: National League (id=48), WSL (id=736), Scottish Championship/L1/L2
   - Parallelise all 18 league calls with `Promise.all()`
   - Return HTTP 500 on full failure
   - Remove investigation `console.log` statements

4. **Add `.gitignore`** — Before anyone runs `npm install` locally. Minimum: `node_modules/`, `.env`, `.env.local`, `.DS_Store`

5. **Verify Supabase RLS** — Confirm Row Level Security is enabled on `matches`, `profiles`, and any other tables. Required for safe launch.

### Medium Priority

6. **Update Supabase anon key comment** — Change `// Hardcoded fallbacks for testing — remove before production` to `// Public anon key — safe for client-side. RLS policies enforce access control.` The current comment is misleading and creates unnecessary anxiety.

7. **Clean up duplicate `:root` block** — A second minified `:root` at ~line 294 of `index.html` is a harmless legacy artifact from a prior file merge. Safe to remove.

8. **Wire the Offers screen** — Connect `loadOffers()` to Supabase `pitchside_offers` table so real-time offer data shows instead of `OFFERS_FALLBACK`. This directly affects revenue.

### Lower Priority (Pre-launch or Post-launch)

9. **Wire live match data** — Connect Match Detail timeline, lineups, player stats to API-Football. Currently all static prototype data.

10. **Wire league tables** — Connect to API-Football standings endpoint.

11. **Match Day Hub data sources** — Pubs (fan-report system needs backend), Tickets (StubHub/Viagogo affiliate API integration), Transport (TfL API), Food (Google Places API). These are the most complex features to fully wire.

12. **AI Bet Generator backend** — The UI is complete. Needs a backend service that analyses fixture data and generates structured bet suggestions. Could use Claude API to generate reasoning paragraphs given structured match stats.

13. **Odds data feed** — The Odds Comparison ranking needs a live bookmaker odds API (e.g. The Odds API, OddsPortal, or direct bookmaker feeds). Currently shows static fallback.

14. **In-Play Bet Tracker** — Needs: a way to record placed bets (Supabase), a live score feed to evaluate leg status, real-time updates via Supabase Realtime or polling.

15. **Remove stale files** — `rundown-phase-a.html` (215 KB, superseded), `team-ids.txt`, `fetch-team-ids.js` may still be in the repo. Check and delete.

---

## 13. Repository Reference

```
pitchside-backend/                  GitHub: pitchside-app26/pitchside-backend
├── index.html                      The entire app (243 KB, do not edit casually)
├── api/sync.js                     Vercel serverless — fixture sync
├── vercel.json                     Cron: 06:00 + 12:00 UTC daily
├── package.json                    ESM, axios + supabase-js
├── design-tokens.css               v1.0 token definitions (not yet applied to components)
├── existing-tokens.md              Inventory of 24 existing CSS tokens
├── data-update-summary-2025-26.md  Full team change log + update guide
├── CLAUDE-HANDOFF.md               Technical handoff (git history, branch state, code details)
└── cleanup-report-section-[a-h].md 8 reports covering all code quality issues
```

**Active branch for all development: `main`**
**Open diagnostic branch: `sync-investigation`** (do not merge until investigation is complete)

**Git rules:**
- Remote branch delete returns HTTP 403 — delete remote branches via GitHub web UI only
- `build.py` is NOT in the repo — all frontend edits go directly to `index.html`
- When the product owner rebuilds locally with `build.py`, the rebuilt `index.html` must be committed to the repo

---

## 14. How to Use This Document in a New Claude Conversation

Start the conversation with:

> "I'm building a football companion app called Pitchside / The Rundown. I'm pasting in the full product overview document so you understand exactly what's been built and what's outstanding. Please read it carefully before we start. [paste this document]"

Then state which item from Section 12 you want to work on, or describe any new feature you want to add.

For technical git/code history details, also load `CLAUDE-HANDOFF.md` which covers all past commits, code changes, and open branches in full detail.

---

*Pitchside — The Rundown · Product Overview v1.0 · 2026-05-08*
