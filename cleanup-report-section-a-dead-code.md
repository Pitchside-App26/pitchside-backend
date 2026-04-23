# Cleanup Report — Section A: Dead Code Inventory

---

## A1. CSS — Dead classes in `phase-a-styles.css`

### `#auth-onboard1c` selector — line 129
```css
#auth-onboard1c,
```
**Confidence: HIGH.** The `auth-onboard1c` screen was removed in the onboarding redesign. The CSS selector on line 129 still includes it in the `flex-direction: column !important` rule block. The element no longer exists in the DOM.

---

### `.ob-search-wrap` and `.ob-search` — lines 155–168
```css
.ob-search-wrap { ... }
.ob-search { ... }
.ob-search::placeholder { ... }
```
**Confidence: HIGH.** These classes are defined but never used anywhere in HTML or JS. The actual search inputs use `.ob1a-search-input` inside `.ob1a-search-row`. Zero grep hits in all non-CSS files.

---

### `.ob-league-hdr` — lines 169–174
```css
.ob-league-hdr { ... }
```
**Confidence: HIGH.** Defined but never referenced. League headers in the two-panel layout use `.ob1a-search-lg-hdr` (rendered dynamically in `renderMyClubList` and `ob1bRenderTeamList`). Zero grep hits in all non-CSS files.

---

### `.ob-team-row`, `.ob-team-row.selected`, `.ob-team-name`, `.ob-team-row.selected .ob-team-name`, `.ob-check`, `.ob-team-row.selected .ob-check` — lines 175–196
```css
.ob-team-row { ... }
.ob-team-row:active { ... }
.ob-team-row.selected { ... }
.ob-team-name { ... }
.ob-team-row.selected .ob-team-name { ... }
.ob-check { ... }
.ob-team-row.selected .ob-check { ... }
```
**Confidence: HIGH.** These pre-redesign team-row classes are never used. The new two-panel layout uses `.ob1a-team-card`, `.ob1a-team-name`, `.ob1a-tick`. Zero grep hits across all HTML and JS source files.

---

## A2. CSS — Dead classes in `rundown-base.html`

### `.jump-bar` and `.jump-btn` — lines 698–707
```css
.jump-bar { width: 375px; display: flex; ... }
.jump-btn { font-family: var(--fm); ... }
.jump-btn:hover { ... }
.jump-btn.on { background: var(--live); ... }
```
**Confidence: HIGH.** The `<div id="jumpBar">` element was removed from the HTML in NAV-1. `buildJumpBar()` null-guards with `if (!bar) return;` so these classes are never applied. The CSS block can be removed.

---

### `.tabs` and `.ti` — lines 107 (pretty) and 338 (minified)
```css
.tabs { position: absolute; bottom: 0; ... height: 78px; ... }
.ti { flex: 1; ... }
.ti .ico { ... }
.ti .lbl { ... }
.ti.on .lbl { ... }
```
**Confidence: HIGH.** All per-screen `.tabs` divs (previously on n0, n4, n11, n12, n13) were removed in NAV-1. The new bottom navigation uses `.rundown-nav` from `nav-1-styles.css`. The old `.tabs`/`.ti` classes are now dead. Note: these appear twice in `rundown-base.html` (pretty at ~line 107, minified at ~line 338) — both instances are dead.

---

### `.screen`, `.screen.on`, `:root`, `body` — triple-defined in `rundown-base.html`
**Confidence: HIGH (duplication, not strictly dead).** `:root` is defined at line 12 and again at line ~294. `.screen` / `.screen.on` appear at lines 90–91, 329–330, and 670–671. `body{}` appears at lines ~40 and ~308. The latter definitions in the minified block (~line 294 onward) appear to be a second full CSS block present in the file, likely from a prior merge of two HTML versions. The final `.screen` override at line 670–671 is a "combined file override" comment. All three definitions of `.screen` are identical, so two of the three are dead weight. Flagged here as a duplication risk rather than outright dead code — removing the wrong one could break the prototype.

---

## A3. JavaScript — Dead/unreachable code

### `goToScreen()` in `phase-a-additions.js` — line 486
```js
function goToScreen(screenId) { ... }
```
**Confidence: HIGH.** This function is never called from any HTML `onclick` attribute or from any other JS function across all source files. It bridges auth screen IDs to numeric `goTo()` — functionality covered by `showAuthScreen()` and direct `goTo()` calls. Safe to remove.

---

### `AUTH_SCREEN_IDS` array in `nav-1-scripts.js` — lines 22–26
```js
var AUTH_SCREEN_IDS = [
  'auth-login', 'auth-register',
  'auth-onboard1a', 'auth-onboard1b', 'auth-onboard1c',
  'auth-onboard2'
];
```
**Confidence: HIGH (two issues).**
1. The variable `AUTH_SCREEN_IDS` is declared but never referenced anywhere in `nav-1-scripts.js` or any other file.
2. It still contains `'auth-onboard1c'` which was removed in the onboarding redesign.

The array is dead code and should be removed entirely.

---

### `buildJumpBar()` call overhead in `rundown-base.html` — lines 2040, 2051
```js
buildJumpBar();        // called inside goTo() on every screen change
buildJumpBar(); goTo(0); // called on initial load
```
**Confidence: LOW (harmless but wasteful).** `buildJumpBar()` is still called on every screen navigation. It immediately returns because `document.getElementById('jumpBar')` is null. The function call is a no-op but runs on every `goTo()` invocation. The call at line 2040 inside `goTo()` and at line 2051 on startup both fire and do nothing. Low priority.

---

### `const` inside `initSupabase()` in `phase-a-additions.js` — lines 18–19
```js
const SUPABASE_URL = 'https://vmwcumegngppqojetfvv.supabase.co';
const SUPABASE_KEY = 'eyJhbG...';
```
**Confidence: N/A — style inconsistency (see Section C), not dead code.** Flagged here because the comment says "remove before production" — these constants are live and functional but should not remain in the codebase long-term.

---

## A4. HTML — Dead/vestigial elements

### Static placeholder content in `n13` profile screen — `rundown-base.html` lines 1844–1960
**Confidence: MEDIUM.** The entire static profile screen content ("James D.", Arsenal/Liverpool teams, Bet365/Sky Bet toggles) is meant to be replaced at runtime by `updateProfileScreen()`. However, `updateProfileScreen()` targets `document.getElementById('profile-dynamic')`, and **that element does not exist anywhere in `rundown-base.html`**. The function contains `if (!container) return;` so it silently no-ops. This means:
- On login: the profile screen is never dynamically updated
- The static "James D." prototype content is always shown instead

This is likely a bug introduced when n13 was built as a static prototype — the `id="profile-dynamic"` wrapper was never added to the screen. Flagged as **needs human review** — either add `<div id="profile-dynamic">...</div>` wrapping the scroll content, or the static content is intentionally left as the visual prototype and the dynamic update is a future feature.

---

### `versel.json` — repo root
**Confidence: HIGH (wrong filename, not dead code per se).** The Vercel configuration file is named `versel.json` (typo) instead of `vercel.json`. Vercel will not read it. The cron job (`/api/sync` every 30 minutes) is therefore not configured. This should be renamed.

---

## A5. Backend — `api/sync.js`

### Module syntax mismatch — line 27
```js
const { createClient } = require('@supabase/supabase-js');  // CommonJS
...
export default async function handler(req, res) { ... }     // ESM
```
**Confidence: HIGH (runtime bug).** The file uses CommonJS `require()` imports but `export default` ESM export syntax. These are incompatible. The function will fail to deploy/run as-is. Either:
- Change to `module.exports = async function handler(...)` (CommonJS), or
- Change `require()` to `import` statements (ESM) and add `"type": "module"` to `package.json`

Vercel Node.js serverless functions default to CommonJS. The `export default` pattern is used in Vercel Edge Functions — this file appears to be a serverless function, so the fix is to use `module.exports`.

---

## A6. Stale build artifacts / development files

### `rundown-phase-a.html` — 3,827 lines, ~215 KB
**Confidence: HIGH (stale).** This is a prior-phase build output. It is not referenced by `build.py`, not deployed, and superseded by `index.html`. It is tracked in git, adding ~215KB of noise. Candidate for deletion or gitignore.

### `team-ids.txt` — repo root
**Confidence: HIGH (development artifact).** Output of `fetch-team-ids.js`. The team IDs it contains have already been incorporated into `TEAM_IDS` in `phase-a-additions-2.js`. This file has no runtime purpose. Candidate for gitignore or deletion.

### `app/` directory — empty
**Confidence: HIGH (empty).** The `app/` directory contains no files. It was presumably a placeholder. Can be removed.

---

*End of Section A. Sections B–H to follow.*
