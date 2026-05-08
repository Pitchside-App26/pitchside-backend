# Claude Handoff Document — Pitchside / The Rundown
*Generated 2026-05-08. Paste this entire document at the start of a new Claude conversation.*

---

## 1. What This Project Is

**The Rundown** is a single-page football companion app for UK users. It is pre-launch. The app lives in a single built HTML file (`index.html`) and is deployed on Vercel with a Supabase backend.

The app has:
- An age gate / onboarding flow (team selection, bookmaker preferences)
- A live scores screen
- A fixtures screen
- An odds comparison screen (bookmaker offers)
- A user profile / settings screen
- Supabase auth (email + password)

The product owner builds `index.html` locally using a `build.py` script that stitches together source files. That script is **not in this repository** — it lives only on the product owner's local machine. The repo contains only the **built output** (`index.html`) and the backend (`api/sync.js`).

---

## 2. Repository Structure

```
pitchside-backend/
├── index.html                          ← The entire app. Single built file. ~243 KB.
├── api/
│   └── sync.js                         ← Vercel serverless function. Fetches fixtures from API-Football → Supabase.
├── vercel.json                         ← Vercel config. Cron schedule for /api/sync.
├── package.json                        ← ESM, axios + supabase-js dependencies.
├── design-tokens.css                   ← Design token definitions (standalone). NOT injected by build yet.
├── existing-tokens.md                  ← Inventory of the 24 CSS custom properties in index.html.
├── data-update-summary-2025-26.md      ← Full 2025/26 season team data changelog.
├── cleanup-report-section-a-dead-code.md
├── cleanup-report-section-b-duplication.md
├── cleanup-report-section-c-inconsistencies.md
├── cleanup-report-section-d-security.md
├── cleanup-report-section-e-code-quality.md
├── cleanup-report-section-f-documentation.md
├── cleanup-report-section-g-stale-files.md
├── cleanup-report-section-h-build-pipeline.md
└── README.md                           ← Empty placeholder.
```

**Source files that build index.html (on product owner's local machine, NOT in repo):**
- `rundown-base.html` — base HTML shell (this file IS in repo as a read-only reference copy)
- `phase-a-styles.css`
- `phase-a-screens.html`
- `phase-a-additions.js`
- `phase-a-additions-2.js`
- `nav-1-styles.css`
- `nav-1-scripts.js`
- `phase-b-styles.css`
- `phase-b-scripts.js`

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla JS (`var/function` style), plain HTML/CSS. No framework. |
| Auth / Database | Supabase (anon key hardcoded client-side — this is intentional and safe for the anon role; see Section D of cleanup reports) |
| Backend function | Vercel serverless (ESM, Node.js) |
| Fixture data | API-Football v3 (`https://v3.football.api-sports.io`) |
| Deployment | Vercel (Hobby tier) |
| Cron | Vercel cron — runs `/api/sync` at 06:00 UTC and 12:00 UTC daily |
| Fonts | Playfair Display, Instrument Sans, IBM Plex Mono (existing), Source Serif Pro / Inter / JetBrains Mono (v1.0 design tokens, not yet applied) |

---

## 4. Git History — What Has Been Done

All work is committed to `main` unless noted. Commits in chronological order (oldest first):

### Branch: `data-update-2025-26` (merged to main)
Updated ALL_TEAMS and LEAGUE_INFO in index.html for the 2025/26 season.

- Separate commit per league: PL (20), Championship (24), L1 (24), L2 (24), National League (24, **new**), WSL (12, **new**), Scottish Prem (12), Scottish Champ (10), Scottish L1 (10), Scottish L2 (10)
- Added `'NATIONAL LEAGUE'` and `"WOMEN'S SUPER LEAGUE"` entries to LEAGUE_INFO
- Added season comment: `// Season: 2025/26 — review June 2026`
- Created `data-update-summary-2025-26.md` with full change log and a "how to update next summer" guide
- Product owner confirmations: Peterhead (Scottish L1) confirmed HIGH confidence; Sun Bets never existed in codebase (shut down 2017, pre-dates this code)
- All 22 bookmakers verified by product owner

### Branch: `batch-2-bug-fixes` (merged to main)
Fixed four bugs from Section E of the cleanup reports.

**E3 — `saveAllOnboardingData()` silently discards data:**
Added an explicit session check at the top of the function. If `!sbClient || !authUser`, it now calls `showToast('Session expired — please log in again', 'error')` and redirects to auth-login instead of silently returning.

**E5 — Auth flash (logged-out UI shown before session loads):**
Added `var _authChecking = false` flag. In `initSupabase()`, flag is set to `true` before `checkAuthState()` is called, and `false` after the `getSession()` promise resolves. In `updateProfileScreen()`, if `_authChecking` is true when no `authUser` is present, it renders a loading placeholder instead of the logged-out state.

**E6 — XSS via unescaped email in innerHTML:**
Added `escHtml()` helper function:
```js
function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
```
Applied to `authUser.email` before all innerHTML insertion points in `updateProfileScreen()`.

**E8 — Missing `.catch()` on async chains:**
Added `.catch()` handlers to both the outer and inner promise chains in `loadUserProfile()` to surface rejections to Vercel logs rather than silently swallowing them.

### Branch: `batch-3-cleanup` (merged to main)
Three categories of cleanup.

**Category 1 — Stale file deletions:**
- Deleted `versel.json` (typo of `vercel.json` — Vercel never read it; the real `vercel.json` was already correct)
- Deleted empty `app/` directory

**Category 2 — Dead code removal:**
Dead CSS removed from index.html:
- `#auth-onboard1c` selector (screen removed in onboarding redesign)
- `.ob-search-wrap`, `.ob-search`, `.ob-search::placeholder` (zero usages)
- `.ob-league-hdr` (zero usages)
- `.ob-team-row` and all sub-selectors (6 rules, pre-redesign, zero usages)
- `.jump-bar` and `.jump-btn` (element removed in NAV-1)
- `.tabs` and `.ti` (both copies — pretty at ~line 107, minified at ~line 338)

Dead JS removed from index.html:
- `goToScreen()` function (never called anywhere)
- `AUTH_SCREEN_IDS` array (declared, never referenced; also contained removed screen ID)

**Category 3 — Bookmaker list consolidation (Section B2):**
Replaced three separate parallel arrays with a single master source of truth:
```js
var BOOKMAKERS = [
  { name: 'Bet365', url: 'https://www.bet365.com/', licence: '39563' },
  // ... 22 total entries
];
var ALL_BOOKMAKERS  = BOOKMAKERS.map(function(b) { return b.name; });
var AFFILIATE_URLS  = {};
var BOOKIE_LICENCES = {};
BOOKMAKERS.forEach(function(b) {
  AFFILIATE_URLS[b.name]  = b.url;
  BOOKIE_LICENCES[b.name] = b.licence;
});
```

**Deferred (NOT done):** `updateProfileScreen()` deletion. This function targets `getElementById('profile-dynamic')` which does not exist in the HTML — it always silently no-ops. However it has 12+ call sites (including ones added in Batch 2). The correct fix is to either (a) add a `<div id="profile-dynamic">` wrapper around the scrollable content of screen `#n13`, making the function actually work, or (b) delete the function and all 12+ call sites. This was deferred because it requires a coordinated HTML + JS change.

### Branch: `design-tokens-foundation` (merged to main)
Established the v1.0 design system token foundation.

**Step 1:** Created `existing-tokens.md` — a full inventory of the 24 existing CSS custom properties currently in `index.html`:
- Backgrounds: `--parchment`, `--parchment2`, `--parchment3`, `--card`
- Text: `--ink` (225 uses!), `--ink2`, `--ink3`, `--ink4`, `--ink5`
- Brand: `--live`, `--live-bg`, `--forest`, `--forest-bg`, `--gold`, `--gold-bg`
- League: `--pl`, `--ucl`, `--racing`, `--pitch`
- Borders: `--rule` (86 uses), `--rule-strong`
- Fonts: `--fd`, `--fs` (119 uses), `--fm` (137 uses)

**Step 2:** Created `design-tokens.css` — the v1.0 design token file with 62 new tokens in `:root`. These are a **dark-mode** design system (opposite polarity to the existing light/warm palette). Categories: backgrounds (4), text (4), brand (3), semantic (4), borders (3), interactive (3), font stacks (3), type scale (8), weights (4), line heights (3), spacing (10 — 8pt grid), radius (5), animation (5), shadows (3).

**Zero name collisions** between old 24 tokens and new 62 tokens.

**Step 3:** Injected the 62 new tokens as the first `:root` block in `index.html`'s `<style>` tag (before the existing `--parchment` block). The injection is inline because `build.py` is not in the repo. An inline comment marks where `build.py` should inject `design-tokens.css` when the build pipeline is eventually committed:
```css
/* build.py note: when build pipeline is restored, inject design-tokens.css
   as the first entry in the CSS array, before phase-a-styles.css. */
```

**Decision: No token migration.** The new tokens are added alongside the old ones. No components have been migrated from `--ink`/`--parchment` to `--text-primary`/`--bg-primary`. Migration is a future phase. The existing app still uses the old light/warm palette exclusively.

### Direct commits to `main`
- `7cd3bc2` — Changed `vercel.json` cron from `*/30 * * * *` (Hobby-tier non-compliant) to two entries: `0 6 * * *` and `0 12 * * *` (06:00 and 12:00 UTC daily)

---

## 5. Current State of Key Files

### `vercel.json`
```json
{
  "crons": [
    { "path": "/api/sync", "schedule": "0 6 * * *" },
    { "path": "/api/sync", "schedule": "0 12 * * *" }
  ]
}
```

### `package.json`
```json
{
  "name": "pitchside-backend",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@supabase/supabase-js": "latest",
    "axios": "latest"
  }
}
```
Note: `"type": "module"` is intentional and required — it enables ESM for Vercel serverless functions. `api/sync.js` uses `import`/`export default`.

### `api/sync.js` — CURRENT STATE (with investigation logging)
The file currently has temporary `console.log` lines added for a diagnostic investigation. These are on the `sync-investigation` branch (commit `f5f2097`) which has **not been merged to main**. Main still has the clean version without logging.

The function:
- Queries `GET https://v3.football.api-sports.io/fixtures` with `date: today` (today's date only) and `season: 2025`
- Loops over 18 league IDs
- Upserts results into Supabase `matches` table with `onConflict: 'id'`
- Returns HTTP 200 always with `{ message, date, total_matches_synced, errors }`

**Known architectural problems with sync.js (investigation in progress — see Section 8):**
1. `date: today` only — function fetches only today's fixtures. On non-match days, `total_matches_synced` is 0 and the function looks healthy while doing nothing.
2. No lookback — yesterday's final scores never get a status update after midnight.
3. No lookahead — future fixtures (tomorrow, this weekend) never appear in Supabase.
4. No staleness detection — every run blindly overwrites existing rows.
5. Always returns HTTP 200 even when all 18 leagues fail.
6. National League, WSL, Scottish Championship/L1/L2 were added to ALL_TEAMS in the data update but are NOT in the LEAGUES array in sync.js — they will never be synced.

---

## 6. Open Branches

| Branch | Status | Purpose |
|---|---|---|
| `main` | Current production branch | All merged work |
| `sync-investigation` | Open, NOT merged | Temporary logging added to api/sync.js for diagnostic. Revert or extend depending on log findings. |
| `claude/build-user-auth-MbSij` | Old, open | Appears to be an earlier Claude session branch. Likely stale. |
| `critical-bug-fixes` | Old, open | Appears to be an earlier batch. May be superseded by batch-2. |

Remote branches that have been merged and can be deleted via GitHub UI:
`origin/batch-2-bug-fixes`, `origin/batch-3-cleanup`, `origin/data-update-2025-26`, `origin/design-tokens-foundation`

(Remote branch deletion returns HTTP 403 from this git server — delete these via GitHub web UI, not via `git push origin --delete`.)

---

## 7. Cleanup Reports — What's Been Done From Each

Eight cleanup reports exist in the repo root (`cleanup-report-section-a` through `h`). Here is the status of every item:

### Section A — Dead Code
| Item | Status |
|---|---|
| A1: Dead CSS in `phase-a-styles.css` (`#auth-onboard1c`, `.ob-search-*`, `.ob-league-hdr`, `.ob-team-row` et al) | **DONE** (batch-3) |
| A2: Dead CSS in `rundown-base.html` (`.jump-bar`, `.tabs/.ti` × 2) | **DONE** (batch-3) |
| A3: `goToScreen()` dead function | **DONE** (batch-3) |
| A3: `AUTH_SCREEN_IDS` dead array | **DONE** (batch-3) |
| A3: `buildJumpBar()` no-op calls | **DEFERRED** — harmless no-ops, low priority |
| A3: `const` inside `initSupabase()` style inconsistency | **DEFERRED** — cosmetic |
| A4: Static profile screen `#profile-dynamic` missing wrapper | **DEFERRED** — needs design decision (see Section 9 below) |
| A4: `versel.json` typo | **DONE** (deleted in batch-3) |
| A5: `api/sync.js` module syntax mismatch | **DONE** (fixed in an earlier session — now uses ESM throughout) |
| A6: `rundown-phase-a.html` stale artifact | **NOT DONE** — still in repo (215 KB noise) |
| A6: `team-ids.txt` development artifact | **NOT DONE** — may no longer exist (check `ls`) |
| A6: `app/` empty directory | **DONE** (deleted in batch-3) |

### Section B — Duplication
| Item | Status |
|---|---|
| B1: Duplicate `:root` block (minified copy) | **NOT DONE** — second `:root` at ~line 294 of index.html still present |
| B1: `.screen`/`.screen.on` defined 3× | **NOT DONE** |
| B1: `body {}` defined 2× | **NOT DONE** |
| B2: Bookmaker list duplicated across 4 locations | **DONE** (batch-3) |
| B3: Two bookmaker toggle components with different CSS | **NOT DONE** — cosmetic, medium risk |
| B4: `ob1bRenderTeamList()` near-identical rendering paths | **NOT DONE** — low priority |
| B5: Three `window.addEventListener('load', ...)` handlers | **NOT DONE** — low priority |
| B6: Bookmaker accent colours in OFFERS_FALLBACK vs Supabase | **NOT DONE** — self-resolves when Supabase goes live |

### Section C — Inconsistencies
| Item | Status |
|---|---|
| C1: `var/function` vs ES6 mixed style | **NOT DONE** — cosmetic, low priority |
| C2: Four different CSS prefix schemes | **NOT DONE** — cosmetic, document as convention |
| C3: Two different HTML escaping approaches | **NOT DONE** — low priority |

### Section D — Security
| Item | Status |
|---|---|
| D1: Hardcoded Supabase anon key with stale comment | **NOT DONE** — comment says "remove before production" but key is actually safe for client-side use. Should update the comment. |
| D2: No `.gitignore` | **NOT DONE** — no `.env` or `node_modules` yet so no immediate harm, but should be added |
| D3–D5: (see cleanup-report-section-d.md for full list) | Review file for remaining items |

### Section E — Code Quality
| Item | Status |
|---|---|
| E1: Long functions that should be split | **NOT DONE** — refactoring, low priority |
| E2: Missing null checks on DOM queries | **NOT DONE** |
| E3: `saveAllOnboardingData()` silent data loss | **DONE** (batch-2) |
| E4: `_installGoToWrapper()` 300ms setTimeout fragility | **NOT DONE** |
| E5: Auth flash on profile screen | **DONE** (batch-2) |
| E6: XSS via unescaped email | **DONE** (batch-2) |
| E7: Birmingham City in two leagues in ALL_TEAMS | **DONE** (data-update — resolved by 2025/26 data; Birmingham is in Championship, not PL) |
| E8: Missing `.catch()` on async chains | **DONE** (batch-2) |
| E9: `hexToRgba()` silent failure | **NOT DONE** |

### Sections F, G, H
- **F (Documentation):** All items are about adding comments / docs. None done. Low priority.
- **G (Stale files):** `versel.json` and `app/` deleted. `rundown-phase-a.html`, `team-ids.txt`, `fetch-team-ids.js`, `rundown-phase-b.html` status uncertain — check `ls` in repo root.
- **H (Build pipeline):** All items are about `build.py` which is not in the repo. The relevant finding: design-tokens.css injection order is documented with an inline comment in index.html.

---

## 8. The Sync Investigation (Current Open Task)

This is the most important active task. We are trying to determine whether `api/sync.js` is actually pulling fresh data from API-Football or silently doing nothing.

**Branch:** `sync-investigation` (commit `f5f2097`) — already pushed to origin.

**What we added:** Detailed `console.log` statements that will appear in Vercel function logs:
```
[sync] START — date=... season=... leagues=18
[sync] ENV CHECK — FOOTBALL_API_KEY=SET/MISSING SUPABASE_URL=SET/MISSING SUPABASE_SERVICE_ROLE_KEY=SET/MISSING
[sync] league=39 http=200 api_results=0 fixture_count=0 response_bytes=142 api_errors={}
[sync] league=39 — no fixtures for 2026-05-08, skipping upsert
[sync] league=39 UPSERT OK — rows_submitted=5 rows_affected=5
[sync] league=39 UPSERT ERROR — <message> code=<code>
[sync] league=39 EXCEPTION — <message> http_status=401 body=...
[sync] DONE — total_synced=0 error_count=0 errors=[]
```

**What we need the product owner to do:**
1. The branch is already pushed. Vercel should have created a preview deployment automatically.
2. In Vercel dashboard → Deployments, find the `sync-investigation` preview deployment URL.
3. Visit `https://[preview-url]/api/sync` in a browser (or `curl` it).
4. Go to Vercel → Functions → `api/sync` → Logs and copy the `[sync]` lines.
5. Paste the raw log output back into the Claude conversation.

**What we expect to find and what it means:**

- If `ENV CHECK` shows `FOOTBALL_API_KEY=MISSING` → The API key is not set in Vercel environment variables. This is why sync never works. Fix: add `FOOTBALL_API_KEY` in Vercel → Settings → Environment Variables.
- If `api_errors={"token":"Error/Missing application key"}` with `http=200` → API key is present but invalid/wrong.
- If all leagues show `fixture_count=0` with valid auth → The `date: today` window is the problem. On non-match days there are genuinely no fixtures. This is a **design flaw** — the function needs a date window, not just today.
- If `UPSERT ERROR` lines appear → Supabase schema mismatch (the `matches` table columns may not match what sync.js is trying to write).

**After getting the logs**, the next task is a sync.js rewrite. The planned improvements are:
1. Change `date: today` to a date window (e.g., yesterday through next 7 days) using `from` and `to` params
2. Run two modes: a "fixtures" fetch (upcoming matches, run daily) and a "live scores" fetch (run more frequently during match windows)
3. Add the 5 missing leagues (National League id=48, WSL id=736, Scottish Championship/L1/L2)
4. Return HTTP 500 when all leagues error, not always HTTP 200
5. Remove the investigation logging once findings are confirmed

---

## 9. The `updateProfileScreen()` Decision (Deferred)

This is the most significant deferred issue. The situation:

- `updateProfileScreen()` is a function that builds the logged-in profile screen HTML dynamically
- It targets `document.getElementById('profile-dynamic')`
- That element **does not exist** in `index.html`'s `#n13` screen HTML
- The function has `if (!container) return;` at the top — so it always exits silently
- The static "James D." prototype content in `#n13` is always shown instead
- The function has 12+ call sites (including ones added in batch-2's auth fixes)

**The two options:**
- **Option A (make it work):** Add `<div id="profile-dynamic">` as a wrapper around the scrollable content of `#n13` in index.html. The dynamic function will then actually run and populate the profile screen with real auth data.
- **Option B (remove it):** Delete `updateProfileScreen()` and all 12+ call sites. Keep the static prototype screen.

Option A is almost certainly the right answer — the function exists and is fully implemented, it just has a missing HTML hook. This should be the next batch after the sync investigation is resolved.

---

## 10. Known Constraints and Gotchas

**Single built file:** `index.html` is 243 KB and is the entire frontend. All edits to the frontend are made directly to this file in Claude Code. When the product owner rebuilds locally with `build.py`, their built output must be committed to the repo to take effect. There is a risk of divergence if both Claude Code and the product owner edit index.html independently.

**No `.gitignore`:** If anyone runs `npm install` locally, `node_modules/` will appear uncommitted and could accidentally be staged. Add a `.gitignore` before that happens.

**Vercel Hobby tier limits:**
- Cron: maximum one execution per day per path on Free tier; Hobby tier allows more but `*/30 * * * *` was non-compliant — now set to twice daily.
- Function timeout: 10 seconds on Hobby. The sync function loops 18 leagues sequentially — if API-Football is slow, it may timeout. Consider `Promise.all()` for parallel requests.
- API-Football free tier: 100 calls/day. 18 leagues × 2 runs/day = 36 calls. Leaves 64 for testing/other.

**Remote branch delete returns 403:** `git push origin --delete <branch>` is blocked on this server. Delete remote branches via GitHub web UI only.

**build.py not in repo:** Any instruction to "update build.py" must instead be applied directly to `index.html`. Leave an inline comment wherever the build pipeline would need to change when it's eventually added to the repo.

**`rundown-base.html` in repo:** This is a reference copy of the HTML shell, not the active file. Do not edit it — edits go to `index.html` only.

**Supabase anon key in source:** `SUPABASE_URL` and `SUPABASE_KEY` (anon) are hardcoded in `index.html`. This is intentional and safe — the anon key is designed to be public and Supabase's RLS policies control access. **The `SUPABASE_SERVICE_ROLE_KEY` is different and must never appear in client-side code** — it only exists as a Vercel environment variable for `api/sync.js`.

**JS style convention:** All addition files use `var` and `function` declarations (not `const`/`let`/arrow functions). When editing inline JS in `index.html`, match the surrounding style of the block you're editing.

**Season constant in sync.js:** `SEASON = 2025` refers to the year the 2025/26 season started. API-Football uses the start year. Do not change to 2026 — that would request the wrong season data.

---

## 11. Recommended Next Steps (In Priority Order)

1. **Complete the sync investigation** — Get the Vercel log output from `sync-investigation` branch preview deployment and paste it back to Claude. This tells us whether the data pipeline is fundamentally broken or just architecturally limited.

2. **Rewrite sync.js** — Based on investigation findings. Key changes: date window (not just today), parallel league fetches, missing leagues added, proper error HTTP status codes, remove investigation logging.

3. **Fix `updateProfileScreen()` / `#profile-dynamic`** — Add the missing `<div id="profile-dynamic">` wrapper to `#n13` in index.html. Test that the profile screen actually populates with the logged-in user's data. This is the most impactful deferred issue.

4. **Add `.gitignore`** — Before anyone runs `npm install` locally. Minimum contents:
   ```
   node_modules/
   .env
   .env.local
   .DS_Store
   ```

5. **Clean up the minified duplicate `:root` block** — The second `:root` at ~line 294 of index.html (Section B1) is harmless but adds noise and confusion. Safe to remove.

6. **Update the Supabase anon key comment** (D1) — Change `// Hardcoded fallbacks for testing — remove before production` to `// Public anon key — safe for client-side use. RLS policies enforce access control.`

7. **Verify RLS is enabled on Supabase tables** — Confirm Row Level Security is on for `matches`, `profiles`, and any other tables. This is a pre-launch security requirement.

8. **Add `Promise.all()` to sync.js** — Once the rewrite is done, parallelize the 18 league API calls to avoid sequential latency and reduce Vercel function timeout risk.

---

## 12. How to Identify Yourself to a New Claude Session

Start the new Claude conversation with this prompt:

> "I'm continuing development of The Rundown, a single-page football app. I'm pasting in a handoff document that covers everything done so far. Please read it carefully before we start. [paste this document]"

Then tell Claude which task from Section 11 you want to tackle first.

---

*End of handoff document. Repo: pitchside-app26/pitchside-backend. Branch for active work: main (or sync-investigation for the current diagnostic task).*
