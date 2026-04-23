# Cleanup Report — Section H: Build Pipeline Integrity

---

## H1. Source file existence check — all inputs confirmed present

`build.py` reads 9 source files. All exist in the repository root:

| Variable | Filename | Exists | Size |
|---|---|---|---|
| `base` | `rundown-base.html` | ✓ | 133 KB |
| `styles_a` | `phase-a-styles.css` | ✓ | 17 KB |
| `styles_b` | `phase-b-styles.css` | ✓ | 5 KB |
| `styles_nav` | `nav-1-styles.css` | ✓ | 2 KB |
| `screens` | `phase-a-screens.html` | ✓ | 10 KB |
| `js1` | `phase-a-additions.js` | ✓ | 24 KB |
| `js2` | `phase-a-additions-2.js` | ✓ | 25 KB |
| `js3` | `phase-b-scripts.js` | ✓ | 24 KB |
| `js4` | `nav-1-scripts.js` | ✓ | 3 KB |

**Result: PASS.** No missing source files.

---

## H2. Injection markers — confirmed present in base HTML

`build.py` relies on four string markers to locate injection points:

| Marker | Used for | Present in base |
|---|---|---|
| `</style>` (first occurrence) | CSS injection | ✓ |
| `</head>` (first occurrence) | Supabase CDN tag | ✓ |
| `</div><!-- /phone -->` | Screen HTML fragments | ✓ (with fallback chain) |
| `</script>` (last occurrence) | All JS injection | ✓ |

The phone-close marker has a three-step fallback chain (lines 78–93 of `build.py`) which suggests it has been fragile historically. The primary marker `</div><!-- /phone -->` is present and stable in the current base HTML.

**Result: PASS.** All markers present.

---

## H3. CSS injection order — confirmed correct

Build injects CSS in this order, all before the first `</style>`:
1. `phase-a-styles.css` — auth, onboarding, toast, profile
2. `phase-b-styles.css` — odds rows, offer cards, compliance strip
3. `nav-1-styles.css` — bottom nav bar, scroll padding

Phase B styles correctly follow Phase A (Phase B references `--live-bg`, `--forest-bg`, `--gold-bg` and `--parchment2` defined in the base `:root`). Nav-1 styles correctly follow Phase B (no cross-dependencies).

**Result: PASS.**

---

## H4. JS injection order — confirmed correct

Build injects JS in this order, before the last `</script>`:
1. `phase-a-additions.js` — Supabase init, age gate, auth, profile
2. `phase-a-additions-2.js` — team data, onboarding logic
3. `phase-b-scripts.js` — odds, offers, Phase B init
4. `nav-1-scripts.js` — nav bar wrappers

Dependencies are satisfied in order:
- `phase-a-additions-2.js` calls `showToast()` (defined in `phase-a-additions.js`) ✓
- `phase-b-scripts.js` references `userProfile` (defined in `phase-a-additions.js`) ✓
- `nav-1-scripts.js` wraps `goTo()` and `showAuthScreen()` (both defined in `phase-a-additions.js`) ✓

One risk: `nav-1-scripts.js` wraps `goTo` via a 300ms `setTimeout` at load time (see Section E4). If `phase-a-additions.js` triggers an auth-state callback before 300ms has elapsed, the original unwrapped `goTo` fires. In practice this is not an issue since auth callbacks involve network round-trips, but the dependency is timing-based rather than explicit.

**Result: PASS with caveat** (E4 timing issue).

---

## H5. Content checks — all 10 pass

The 10 automated checks in `build.py` (lines 127–145) all pass on the current build:

| Check | String searched | Result |
|---|---|---|
| MOCK_ODDS array | `MOCK_ODDS` | ✓ |
| AFFILIATE_URLS | `AFFILIATE_URLS` | ✓ |
| Market tabs element | `id="market-tabs"` | ✓ |
| Offer cards container | `id="offer-cards-container"` | ✓ |
| Odds comparison rows | `id="odds-comparison-rows"` | ✓ |
| Featured offer container | `id="featured-offer-container"` | ✓ |
| Compliance strips | `betting-compliance-strip` | ✓ |
| Bottom nav bar | `class="rundown-nav"` | ✓ |
| NAV_TAB_MAP | `NAV_TAB_MAP` | ✓ |
| Match Day tab | `data-tab="matchday"` | ✓ |

**Result: PASS.**

---

## H6. Files in repo not in build pipeline

These files exist in the repository but are not read by `build.py`:

| File | Type | In build? | Notes |
|---|---|---|---|
| `index.html` | Build output | No (it IS the output) | Deployment target — correct |
| `rundown-phase-b.html` | Build output | No (it IS the output) | Redundant copy of index.html (see G6) |
| `rundown-phase-a.html` | Old build output | No | Stale artifact (see G1) |
| `api/sync.js` | Server function | No | Backend — not part of client build |
| `versel.json` | Config | No | Infra config — not part of client build |
| `package.json` | Node deps | No | Server deps — not part of client build |
| `fetch-team-ids.js` | Dev utility | No | One-time script (see G5) |
| `team-ids.txt` | Dev artifact | No | Already consumed (see G2) |
| `cleanup-report-*.md` | Docs | No | Documentation — correct |

No files that *should* be in the build pipeline are missing from it.

**Result: PASS.**

---

## H7. Build step numbering inconsistency

`build.py` step labels in console output:
- `[1]` Read source files
- `[2]` Insert CSS
- `[3]` Insert Supabase CDN
- `[4]` Insert screen HTML
- `[5/6/7/8]` Insert JS files  ← combined label for 4 JS files
- `[8]` Write output  ← **duplicate of 8**
- `[10]` Content checks  ← skips 9

The write step (`[8]`) and content checks (`[10]`) are mislabelled. Should be `[9]` and `[10]` respectively. Minor cosmetic issue only — does not affect build correctness.

**Result: PASS (cosmetic only).**

---

## H8. Supabase CDN version — unpinned

`build.py` line 71:
```python
cdn = '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>'
```

The `@2` tag resolves to the latest 2.x release. This means a breaking patch or minor release in the Supabase JS v2 SDK would affect the built output on next build without any code change. The `package.json` already pins `@supabase/supabase-js` to `"latest"` for the server side — this is the same pattern client-side.

**Recommendation:** Pin to a specific minor version, e.g. `@supabase/supabase-js@2.49.0`, and update deliberately.

**Result: LOW RISK** — Supabase v2 has been stable; v3 would require an explicit `@3` tag change.

---

*End of Section H. Build pipeline is structurally sound. 8 items reviewed — all checks pass, 3 improvement opportunities noted.*
