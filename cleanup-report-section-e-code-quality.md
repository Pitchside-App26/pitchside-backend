# Cleanup Report — Section E: Code Quality Observations

---

## E1. Functions over 50 lines that should be broken up

### `updateProfileScreen()` — `phase-a-additions.js` lines 200–269 (~70 lines)
Handles three distinct states (no Supabase, not logged in, logged in) and builds the entire logged-in profile HTML via string concatenation inside one function. The logged-in branch alone is ~40 lines of concatenated HTML. Should be split into:
- `_renderProfileLoggedOut(container)`
- `_renderProfileLoggedIn(container, user, profile)`
- `_renderProfileNoConnection(container)`

### `initAgeGate()` — `phase-a-additions.js` lines 55–90 (~36 lines)
Constructs the entire age gate UI as a single inline HTML string (~15 concatenated lines). Hard to read and impossible to update individual elements without touching the whole string. The DOM is also built fresh every page load even though the structure never changes — only the options differ.

### `ob1bRenderTeamList()` — `phase-a-additions-2.js` lines 340–409 (~70 lines)
Four near-identical rendering paths (see Section B4). Each is 15–20 lines. The function is correct but dense. Splitting the inner loop into a shared helper would halve the length.

### `renderOddsComparison()` — `phase-b-scripts.js` lines 278–336 (~58 lines)
Handles sort key selection, sorting, per-row HTML building, and subtitle update in one function. Could extract `_buildOddsRow(row, idx, total, sortKey, userAccounts)` as a pure helper.

---

## E2. Missing null checks on DOM queries

These DOM queries lack null guards before use — they will throw if the element is absent:

### `buildDots()` in `rundown-base.html` line 2014
```js
const dotsEl = document.getElementById('dots');
dotsEl.innerHTML = '';   // throws if #dots missing
```
No `if (!dotsEl) return;` guard. Compare with `buildJumpBar()` which correctly has `if (!bar) return;`.

### `goTo()` in `rundown-base.html` line 2026
```js
document.getElementById(SCREENS[cur].id).classList.remove('on');
```
No null check. If any screen ID in `SCREENS` doesn't exist in the DOM, this throws. Currently all IDs exist, but a future screen addition that forgets an HTML stub would cause a silent crash.

### `tick()` in `rundown-base.html` line 2047
```js
document.getElementById('sbTime').textContent = ...
```
No null check. Minor — `sbTime` is always present in the base HTML.

---

## E3. `saveAllOnboardingData()` silently discards all onboarding data

`phase-a-additions-2.js` lines 541–545:
```js
if (!sbClient || !authUser) {
  hideAuthScreens();
  if (typeof goTo === 'function') goTo(13);
  return;
}
```
If `sbClient` is null (Supabase not initialised) or `authUser` is null at the point `submitBookmakers()` is called, the function silently advances to the profile screen **without saving** the user's club selection, team selections, or bookmaker toggles. The user sees no error. All onboarding data is lost.

This is a real data-loss path. A user who completes the full 3-step onboarding but has a flaky connection at the final step will lose everything silently.

**Fix:** Show a toast error and don't advance: `showToast('Could not save — check your connection', 'error'); return;`

---

## E4. `_installGoToWrapper()` — monkey-patch fires after 300ms setTimeout

`nav-1-scripts.js` lines 76–107:
```js
window.addEventListener('load', function() {
  navBarHide();
  setTimeout(function() {
    _installGoToWrapper();
    _installAuthWrapper();
    updateNavActiveState();
  }, 300);
});
```
The 300ms delay exists to ensure `phase-a-additions.js` has defined `goTo` and `showAuthScreen` before wrapping them. However:

1. If the `load` event fires and `initSupabase()` → `checkAuthState()` → `loadUserProfile()` → `hideAuthScreens()` → `goTo(13)` completes in under 300ms, it will call the **original** unwrapped `goTo`, meaning the nav bar won't show and `syncNavToScreen()` won't fire.
2. The 300ms is an arbitrary delay with no comment explaining why that value was chosen.

**Low probability in practice** (network calls take longer than 300ms), but the pattern is fragile. A cleaner approach would be to check `typeof goTo === 'function'` in a polling loop or use a custom event.

---

## E5. `doLogin()` renders profile screen before data loads

`phase-a-additions.js` lines 390–397:
```js
sbClient.auth.signInWithPassword(...).then(function(result) {
  authUser = result.data.user;
  loadUserProfile();          // async — fires and doesn't wait
  showToast('Welcome back!', 'success');
  hideAuthScreens();
  if (typeof goTo === 'function') goTo(13);  // shows profile immediately
});
```
`loadUserProfile()` is asynchronous — it starts a Supabase query but doesn't await it. The screen navigates to n13 immediately while `userProfile` is still null. `updateProfileScreen()` runs and renders the "not logged in" CTA — until `loadUserProfile()` completes and calls `updateProfileScreen()` again.

**Effect:** Brief flash of the "Sign In / Create Account" CTA after successful login before the real profile loads. Minor UX bug.

**Fix:** Move `hideAuthScreens()` and `goTo(13)` into the `loadUserProfile()` callback, or have `loadUserProfile()` accept a callback parameter.

---

## E6. `updateProfileScreen()` concatenates `authUser.email` without HTML escaping

`phase-a-additions.js` line 253:
```js
'<div class="profile-name">'+(authUser.email || '')+'</div>'
```
And line 237:
```js
var initials = (authUser.email || 'U').substring(0,2).toUpperCase();
```

Email addresses are validated by Supabase before storage, making injection unlikely. However, the email is inserted directly into innerHTML without escaping. If an email somehow contained `<script>` or `<img onerror=...>`, it would execute. Low probability, but easy to fix with a simple text sanitiser.

**Fix:** Use `document.createTextNode()` or a simple `_esc()` call (already defined in `phase-b-scripts.js`) before inserting into HTML strings.

---

## E7. `ALL_TEAMS` data error — 'Birmingham City' in two leagues

`phase-a-additions-2.js`:
- Line 29: `'Birmingham City'` in `'CHAMPIONSHIP'`
- Line 37: `'Birmingham City'` in `'LEAGUE ONE'`

Birmingham City were relegated from the Championship at the end of 2023/24 and play in League One for 2024/25. The Championship entry should be removed. The `TEAM_IDS` entry (line 111: `'Birmingham City':60`) correctly maps to the API-Football ID.

**Effect:** Birmingham City appears twice in search results and in the "All Leagues" browse. A user selecting it from the Championship entry gets the same team, but `leagueOf()` will return `'LEAGUE ONE'` (last match wins in the `forEach`) regardless of which entry they clicked.

---

## E8. Missing error handling on key async paths

| Function | File | Missing |
|---|---|---|
| `checkAuthState()` | `phase-a-additions.js` line 139 | No `.catch()` on `getSession()` promise |
| `loadUserProfile()` | `phase-a-additions.js` line 153 | No `.catch()` — Supabase network failure is silent |
| `loadOffers()` | `phase-b-scripts.js` line 377 | Handled: falls back to `OFFERS_FALLBACK` ✓ |
| `renderOddsComparison()` | `phase-b-scripts.js` line 278 | N/A — synchronous (uses MOCK_ODDS) ✓ |
| `api/sync.js` inner loop | `api/sync.js` line 38 | Handled: per-league try/catch, errors collected ✓ |

`checkAuthState()` and `loadUserProfile()` failures (e.g. network timeout) will silently leave the app in an indeterminate state — `authUser` and `userProfile` will remain null, gating UI will show "locked", but no user-facing error is shown.

---

## E9. `hexToRgba()` — silent failure on malformed input

`phase-b-scripts.js` lines 255–259:
```js
function hexToRgba(hex, alpha) {
  var r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!r) return 'rgba(26,23,20,' + alpha + ')';
  return 'rgba(' + parseInt(r[1], 16) + ...
}
```
If `accent_hex` from Supabase contains a 3-character hex (e.g. `'FFF'`) or has unexpected characters, the regex returns null and the function silently falls back to `rgba(26,23,20,alpha)` (near-black). The offer card would render with a near-black accent instead of the intended colour. No error is logged.

Minor issue — add a `console.warn` on the fallback path for easier debugging.

---

*End of Section E. 9 observations identified (2 should-fix bugs, 5 improvement opportunities, 2 data/minor issues).*
