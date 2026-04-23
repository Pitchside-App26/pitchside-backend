# Cleanup Report — Section F: Documentation Gaps

---

## F1. Files missing header comments

### `api/sync.js`
No header comment of any kind. The file's purpose, schedule, required environment variables, and expected Supabase table schema are undocumented. A new developer opening the file has no context.

**Recommended header:**
```js
/**
 * api/sync.js — Vercel cron handler
 * Fetches today's fixtures from API-Football and upserts into Supabase `matches` table.
 * Schedule: every 30 minutes (configured in vercel.json)
 * Env vars required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FOOTBALL_API_KEY
 */
```

---

### `rundown-base.html`
No file-level comment explaining what this file is, what it contains, or how it fits into the build pipeline. A developer opening it for the first time has no indication that it's a build input (not the deployed file) and that CSS/JS are injected by `build.py`.

**Recommended comment at top of `<head>`:**
```html
<!--
  rundown-base.html — Build input for the Rundown prototype
  DO NOT edit the built output (index.html / rundown-phase-b.html) directly.
  Run build.py to regenerate from this file + phase-a/b/nav-1 fragments.
-->
```

---

### `versel.json` (or `vercel.json` after rename)
No comment is possible in JSON, but the file's sole cron entry has no explanation of what `/api/sync` does or why 30-minute intervals were chosen. Not fixable in JSON, but worth noting in a `README.md`.

---

## F2. Functions without explanatory comments

### `goToScreen()` — `phase-a-additions.js` line 486
No comment. The function bridges auth screen string IDs to the numeric `goTo()` system. It's unclear when a caller should use `goToScreen('auth-login')` vs `showAuthScreen('auth-login')`. The distinction — that `goToScreen` can also route to app screens — is not documented anywhere.

---

### `_installGoToWrapper()` and `_installAuthWrapper()` — `nav-1-scripts.js` lines 76–95
No comment explaining the monkey-patch pattern or why it's needed. The `setTimeout(300)` has no explanation for why 300ms specifically.

**Recommended comment:**
```js
// Wraps the goTo() function defined in rundown-base.html to sync nav state.
// 300ms delay ensures phase-a-additions.js has run and defined goTo/showAuthScreen
// before we wrap them. Load-order is not guaranteed between injected script blocks.
```

---

### `_onboarding` flag — `phase-a-additions.js` line 9
The variable has an inline comment but the comment only describes what it does, not why it exists:
```js
var _onboarding = false;  // true while user is in onboarding — suppresses profile re-render
```
Missing: why suppressing the re-render matters. The reason is that `onAuthStateChange` fires immediately after `signUp()` and would call `updateProfileScreen()` before the onboarding flow finishes, overwriting the auth screen. This is non-obvious and should be documented.

---

### `hexToRgba()` — `phase-b-scripts.js` line 255
No comment. The function's purpose (converting a CSS hex colour to rgba for use as a semi-transparent background on offer badges) is not obvious from the name alone. The fallback to near-black on invalid input is undocumented.

---

### `decimalToFrac()` — `phase-b-scripts.js` line 247
No comment explaining the decimal-to-fractional odds conversion formula. The GCD approach is not immediately obvious to someone unfamiliar with the algorithm.

**Recommended comment:**
```js
// Converts decimal odds (e.g. 2.10) to UK fractional format (e.g. 11/10)
// using GCD reduction. Returns 'EVS' for 1.0 or below.
```

---

### `leagueOf()` — `phase-a-additions-2.js` line 72
No comment. Returns the league name for a given team name, used to pre-select the correct league panel when navigating to onboarding. The `forEach` (rather than early-return) pattern that returns the last match rather than the first is undocumented — relevant given Birmingham City's duplicate entry (see E7).

---

## F3. TODO comments without dates or owners

The codebase has several TODO comments that lack a date or owner, making it impossible to know how old they are or who is responsible:

| File | Line | Comment |
|---|---|---|
| `phase-a-additions.js` | 17 | `// Hardcoded fallbacks for testing — remove before production` |
| `phase-b-scripts.js` | 8 | `// TODO Gate 2: replace all values with real tracked affiliate URLs before going live` |
| `phase-b-scripts.js` | 63 | `// TODO Phase B live: replace MOCK_ODDS with Supabase query when The Odds API is connected` |
| `phase-a-additions-2.js` | 15 | `// Long-term: replace with API-Football /teams.` |

**Recommended format:** `// TODO(owner, YYYY-MM-DD): description` — e.g. `// TODO(Gate 2, 2026-06-01): replace placeholder URLs with tracked affiliate links`

---

## F4. Complex logic blocks without explanation

### `doRegister()` — age re-validation — `phase-a-additions.js` lines 317–321
```js
var dobDate = new Date(dobY, dobM - 1, dobD);
var ageNow  = new Date();
var ageYrs  = ageNow.getFullYear() - dobDate.getFullYear();
if (ageNow < new Date(ageNow.getFullYear(), dobDate.getMonth(), dobDate.getDate())) ageYrs--;
if (ageYrs < 18) { setErr('You must be 18 or over to register.'); return; }
```
The birthday-not-yet-reached adjustment on the fourth line is not commented. A reader could easily mistake `ageNow < new Date(...)` as a bug (comparing Date objects with `<` works but is unexpected).

**Recommended comment:**
```js
// Adjust age down by 1 if birthday hasn't occurred yet this year
```

---

### `checkAgeGate()` — same pattern at lines 107–108
```js
var had = now >= new Date(now.getFullYear(), dob.getMonth(), dob.getDate());
if (!had) age--;
```
Same undocumented birthday-adjustment pattern as above. Both instances need the same one-line comment.

---

## F5. `ALL_TEAMS` — season currency notice is good but incomplete

`phase-a-additions-2.js` lines 14–18:
```js
/* ─────────────────────────────────────────
   ALL_TEAMS
   NOTE: Reflects 2024/25 season.
   Review every summer — promotion/relegation
   changes memberships annually.
   Long-term: replace with API-Football /teams.
───────────────────────────────────────── */
```
This comment is good. However, it does not mention that:
- The data already contains at least one error (Birmingham City in both Championship and League One — see E7)
- Scottish tiers below Premiership have fewer teams than the real league (e.g. Scottish League Two has 10 teams in reality but only 9 are listed)

These are data accuracy gaps, not documentation gaps per se, but worth flagging here.

---

*End of Section F. 5 documentation gap categories, 10 specific items identified.*
