# Cleanup Report — Section C: Inconsistency Inventory

---

## C1. JavaScript style — `var/function` vs ES6 mixed across the codebase

The codebase has two incompatible JS styles coexisting in the same built output:

**ES6 style** — used in `rundown-base.html` inline script (lines ~1965–2057):
- `const`, `let` declarations
- Arrow functions: `() =>`, `s => s.screens.includes(idx)`
- `Array.prototype.includes()`
- `Array.from()`, template literals not present but `.find()` used

**`var/function` style** — used in all injected addition files:
- `phase-a-additions.js`: `var`, `function`, `indexOf() !== -1`
- `phase-a-additions-2.js`: `var`, `function`, `indexOf() !== -1`
- `nav-1-scripts.js`: `var`, `function`, `indexOf() !== -1`

**Exception within `phase-a-additions.js`:** Lines 18–19 inside `initSupabase()` use `const`:
```js
const SUPABASE_URL = 'https://...';
const SUPABASE_KEY = 'eyJ...';
```
This is the only `const` in a file that otherwise uses `var` throughout.

**Impact:** The inconsistency is cosmetic in a browser context (all styles work), but it signals two different authors or two different eras of the codebase. The house standard for addition files is clearly `var/function` — the two `const` declarations in `initSupabase()` should be `var`.

---

## C2. CSS naming conventions — four different prefix schemes in use

| Prefix | Used in | Examples |
|---|---|---|
| `ob1a-` | `phase-a-styles.css` | `.ob1a-team-card`, `.ob1a-league-item`, `.ob1a-search-input` |
| `ob-` | `phase-a-styles.css` (dead) | `.ob-team-row`, `.ob-search-wrap`, `.ob-bookie-row` |
| `oc-` / `oh-` | `rundown-base.html` | `.oc-badge`, `.oc-terms`, `.oh-title`, `.oh-btn` |
| No prefix | `rundown-base.html` | `.bookie-row`, `.bookie-toggle`, `.profile-row`, `.odds-row` |

Phase A added the `ob1a-` prefix convention for the two-panel layout. Phase B added `oc-`/`oh-` for offer cards. The base file uses no prefix for profile and odds rows. The old `ob-` classes (Section A dead code) predate the `ob1a-` convention.

**Impact:** Moderate. No functional bugs, but makes it hard to know which CSS block belongs to which feature. No action needed before launch — document as a convention to adopt consistently in future phases.

---

## C3. Quote style — single vs double quotes inconsistent in HTML attributes

`phase-a-screens.html` and `rundown-base.html` use double quotes for HTML attributes consistently. However, JS-generated HTML in `phase-a-additions.js` and `phase-a-additions-2.js` uses single-quoted JS strings containing double-quoted HTML attributes — which is correct and consistent within those files.

The one inconsistency: `phase-b-scripts.js` `_esc()` function escapes single quotes as `&#39;` and double quotes as `&quot;` before inserting into `onclick` attributes. This is correct for security but the escaping pattern differs from how team names are escaped in `phase-a-additions-2.js` (which uses `.replace(/'/g, "\\'")`). Two different escaping approaches for the same problem.

---

## C4. `build.py` step numbering — step 8 used twice

```python
print("\n[5/6/7/8] Inserting JS files before last </script>…")   # line 97
...
print("\n[8] Writing rundown-phase-b.html…")   # line 108
```

Step 8 is labelled twice — once as part of the combined `[5/6/7/8]` JS insertion header, and again as the standalone output-writing step. This makes the build log confusing. The JS insertion step should be `[5/6/7/8]` and the write step should be `[9]`, with content checks becoming `[10]` (currently correct at `[10]`).

---

## C5. Supabase call pattern — `.then()` vs direct chaining inconsistent

Two patterns are used for Supabase async calls across `phase-a-additions.js`:

**Pattern A — chained `.then()` on the query builder:**
```js
sbClient.from('user_profiles').select('*').eq('id', authUser.id).single()
  .then(function(result) { ... });
```

**Pattern B — direct call then `.then()`:**
```js
sbClient.auth.signUp({ email, password }).then(function(result) { ... });
```

Both are valid but Pattern A (Supabase query builder chaining) always ends in `.then()`. Consistent. The inconsistency is that `loadUserProfile()` chains `.select().eq().single().then()` while `saveAllOnboardingData()` chains `.from().update().eq().then()` — the `.update()` call drops `.single()` correctly. No functional issue.

One genuine inconsistency: `checkAuthState()` uses `.then(function(result) { var session = result.data.session; })` while `doLogin()` uses `.then(function(result) { ... result.data.user ... })`. The destructuring depth differs. Not a bug but worth noting for future additions.

---

## C6. Inline styles on HTML elements that should use CSS classes

Several elements in `phase-a-screens.html` and `rundown-base.html` have layout/sizing styles that belong in CSS:

**`phase-a-screens.html`:**
- `auth-onboard1a` ob-hero: `style="padding:16px 16px 12px;"` (overrides `.ob-hero` default)
- `auth-onboard1b` ob-hero: `style="padding:16px 16px 12px;"`
- `auth-onboard1b` ob-title: `style="font-size:18px;margin-bottom:8px;"` (overrides `.ob-title`)
- Tab buttons inside ob-hero: full inline style strings (~100 chars each) for what are effectively two CSS states

The tab button active/idle styles are particularly problematic — they are set as inline style strings in `ob1bUpdateTabStyles()` in `phase-a-additions-2.js` (lines 284–288), meaning the visual state is entirely managed via JS string manipulation rather than CSS class toggling. This works but is fragile and hard to adjust.

**Recommended pattern:** Add `.ob1b-tab-btn` and `.ob1b-tab-btn.active` CSS classes to `phase-a-styles.css`, then toggle `classList.add/remove('active')` instead of setting `setAttribute('style', ...)`.

**Risk: LOW for cosmetic inline styles. MEDIUM for the tab button refactor** (needs testing of active state transitions).

---

## C7. `rundown-base.html` — two `<style>` blocks with overlapping content

The file contains two separate `<style>` blocks:
1. **Lines ~10–708**: A large pretty-printed CSS block with all base styles
2. **Lines ~292–708**: A second block (inside the first, or immediately following) with minified versions of most of the same rules

This appears to be the result of combining two separate prototype HTML files. The first block contains all the expanded/readable CSS; the second contains a compressed duplicate of much of it plus additional rules specific to the combined prototype (profile, odds, offers).

**Impact:** The built output (`index.html`) inherits this duplication, adding ~15KB of redundant CSS. The second block's definitions win for any conflicting rules (last-write wins in CSS), so the pretty block is partly dead.

---

*End of Section C. 7 inconsistencies identified.*
