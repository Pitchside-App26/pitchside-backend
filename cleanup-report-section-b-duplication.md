# Cleanup Report — Section B: Duplication Inventory

---

## B1. Duplicate CSS blocks in `rundown-base.html`

### `:root` custom properties — defined twice
- **First occurrence:** line 12 (pretty-printed, inside first `<style>` block)
- **Second occurrence:** line ~294 (minified, inside second `<style>` block)

Both blocks define the exact same 16 custom properties (`--parchment`, `--ink`, `--live`, etc.). The second block is identical in content but condensed onto fewer lines. The file appears to have been assembled from two separate HTML files that both contained a full `:root` block.

**Risk of consolidating: LOW.** Safe to remove one — the last definition wins in CSS but they're identical, so removing either copy has no effect.

---

### `.screen` / `.screen.on` — defined three times
- **Line ~90–91** (first `<style>` block, pretty)
- **Line ~329–330** (second `<style>` block, minified)
- **Line ~670–671** (third definition, labelled `/* ── Combined file overrides ── */`)

All three are identical:
```css
.screen { display: none; position: absolute; top: 0; left: 0; right: 0; bottom: 0; }
.screen.on { display: block; }
```

**Risk of consolidating: LOW.** Two of the three can be removed. The "combined file override" at line 670 is the most explicit — it should be the one kept.

---

### `.tabs` / `.ti` CSS — defined twice
- **Line ~107** (first `<style>` block, pretty)
- **Line ~338** (second `<style>` block, minified)

The `.tabs` class is also dead code (see Section A), so both instances should be removed as part of that cleanup.

**Risk of consolidating: LOW** (consolidate with the dead-code removal).

---

### `body {}` rule — defined twice
- **Line ~40** (first `<style>` block)
- **Line ~308** (second `<style>` block, minified)

Both set `font-family`, `background`, `min-height`, `display: flex`, `align-items: center`, `padding`, and `gap`. Second definition overrides first where there's overlap. Effectively identical.

**Risk of consolidating: LOW.**

---

## B2. Bookmaker list duplicated across four locations

The same 22 bookmakers are enumerated separately in four places:

| Location | File | Purpose |
|---|---|---|
| `ALL_BOOKMAKERS` array | `phase-a-additions-2.js` line 494 | Renders onboarding toggle list |
| `AFFILIATE_URLS` object | `phase-b-scripts.js` line 10 | Maps bookie name → click-through URL |
| `BOOKIE_LICENCES` object | `phase-b-scripts.js` line 36 | Maps bookie name → UKGC licence number |
| `OFFERS_FALLBACK` array | `phase-b-scripts.js` line 171 | Per-operator fallback offer data |

Adding a new bookmaker (or removing one) currently requires editing all four locations independently. The objects use the same string keys (`'Bet365'`, `'Sky Bet'`, etc.) with no shared master list to validate against.

**Consolidation approach:** Define a single `BOOKMAKERS` master array of objects, each with `name`, `affiliateUrl`, `licenceNo`, `accentHex`. Derive `ALL_BOOKMAKERS`, `AFFILIATE_URLS`, and `BOOKIE_LICENCES` from it. `OFFERS_FALLBACK` stays separate as it contains offer-specific fields.

**Risk of consolidating: MEDIUM.** The four arrays are in two different JS files injected at different positions in the build. A consolidation refactor needs to ensure the master list is defined before it's referenced by either file. The `OFFERS_FALLBACK` data (which has offer-specific fields like `title`, `subtitle`, `wagering_req`) intentionally diverges and shouldn't be merged into the master list.

---

## B3. Two similar bookmaker toggle components with different CSS

Two separate bookmaker toggle UIs exist with their own class names:

**Onboarding bookmaker list** (`phase-a-additions-2.js` lines 516–521):
```js
'<div class="ob-bookie-row" onclick="toggleBookie(...)">'
'<span class="ob-bookie-name">...</span>'
'<div class="ob-toggle [on]"><div class="ob-toggle-dot"></div></div>'
```
CSS in `phase-a-styles.css`: `.ob-bookie-row`, `.ob-bookie-name`, `.ob-toggle`, `.ob-toggle-dot`

**Profile screen bookmaker list** (`rundown-base.html` static, lines 1886–1904 + `updateProfileScreen()` in `phase-a-additions.js` line 244):
```js
'<div class="bookie-row"><div class="bookie-name">...</div>'
'<div class="bookie-toggle on"><div class="bookie-toggle-dot"></div></div>'
```
CSS in `rundown-base.html`: `.bookie-row`, `.bookie-name`, `.bookie-toggle`, `.bookie-toggle-dot`

The two components look nearly identical visually. The onboarding version uses `ob-` prefix; the profile version uses unprefixed names. They have slightly different dimensions (onboarding toggle: 44×26px; profile toggle: 42×24px).

**Consolidation approach:** Unify on one set of classes. The onboarding `ob-` prefixed version is more explicit; the profile HTML could adopt the same classes.

**Risk of consolidating: MEDIUM.** Requires coordinated change to both JS-generated HTML and CSS in two files. Toggle behaviour is handled differently (onboarding uses `toggleBookie()`, profile uses static `on`/`off` classes). Needs testing.

---

## B4. `ob1bRenderTeamList()` — duplicated rendering logic

In `phase-a-additions-2.js` lines 340–409, `ob1bRenderTeamList()` has four near-identical rendering paths:

1. Watch Live tab, search mode (lines 347–362)
2. Watch Live tab, browse mode (lines 363–373)
3. Follow Scores tab, search mode (lines 376–393)
4. Follow Scores tab, browse mode (lines 394–405)

Each path iterates `ALL_TEAMS`, filters by query, builds `teamCard1bc()` HTML. The only differences are: which array to check for selection (`selectedWatchLive` vs `selectedFollow`), whether to check for WL lock, and which sublabel to show.

**Consolidation approach:** Extract a single inner render loop that accepts `(teams, lgColor, lgName)` and uses `ob1bActiveTab` to resolve selection/lock state inline.

**Risk of consolidating: MEDIUM.** The logic is correct as-is. A refactor could introduce subtle bugs in the lock behaviour. Low priority for a pre-launch product.

---

## B5. Duplicate `window.addEventListener('load', ...)` handlers

Three separate `load` event handlers are registered across the injected JS files:

| File | Handler content |
|---|---|
| `phase-a-additions-2.js` line 575 | `initAgeGate(); initSupabase();` |
| `phase-b-scripts.js` line 548 | `if (typeof initPhaseB === 'function') initPhaseB();` |
| `nav-1-scripts.js` line 98 | `navBarHide(); setTimeout(_installGoToWrapper + _installAuthWrapper, 300)` |

Multiple `load` handlers are technically valid and all fire, but the order of execution is not guaranteed to match file order. The 300ms `setTimeout` in `nav-1-scripts.js` works around this, but it is fragile if init order matters.

**Consolidation approach:** Create a single `onAppLoad()` coordinator function in `rundown-base.html` or a new `app-init.js` that calls all init functions in the correct order.

**Risk of consolidating: MEDIUM.** Would require knowing the correct init order. Current approach works in practice. Low priority.

---

## B6. `LEAGUE_INFO` colors used in onboarding; separate color per-operator in offers/odds

League badge colours are defined once in `LEAGUE_INFO` (`phase-a-additions-2.js` line 86) and reused consistently across both onboarding panels. Good pattern.

However, bookmaker accent colours are duplicated between:
- `OFFERS_FALLBACK` `accent_hex` fields (`phase-b-scripts.js` lines 171–232)
- Supabase `pitchside_offers.accent_hex` column

When Supabase goes live, `OFFERS_FALLBACK` becomes dead data, so this divergence self-resolves. No action needed now.

---

*End of Section B. 6 duplication patterns identified.*
