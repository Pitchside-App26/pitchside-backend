# Existing CSS Custom Properties — The Rundown

Inventory of every CSS custom property currently defined in `index.html`.
Generated April 2026 for reference during design-tokens migration.

---

## Source

Tokens are defined in two `:root` blocks inside the single inline `<style>` tag:
- **Lines 12–37** — pretty-printed (canonical definition)
- **Lines 290–300** — minified duplicate (legacy artifact from prior file merge; values identical)

The minified duplicate is a known issue flagged in cleanup-report-section-b-duplication.md (B1).
Both blocks define the same tokens; the minified one can be removed in a future cleanup pass.

---

## Token inventory (24 tokens)

### Backgrounds / surfaces

| Token | Value | Uses | Primary role |
|---|---|---|---|
| `--parchment` | `#F5F0E8` | 52 | Main app background, modal backgrounds, button text on dark |
| `--parchment2` | `#EDE8DF` | 21 | Hover states on rows, sub-surface backgrounds |
| `--parchment3` | `#E4DDD2` | 2 | Deeper warm background (rarely used) |
| `--card` | `#FDFBF7` | 38 | Card/surface colour — near-white with warmth |

### Text / ink

| Token | Value | Uses | Primary role |
|---|---|---|---|
| `--ink` | `#1A1714` | 225 | Primary text colour — near-black with warmth; also used for filled buttons/backgrounds |
| `--ink2` | `#3D3830` | 1 | Dark secondary text (barely used — effectively redundant) |
| `--ink3` | `#6B6560` | 26 | Mid-tone text, metadata |
| `--ink4` | `#A09890` | 64 | Muted text — labels, captions, inactive |
| `--ink5` | `#C8C2B8` | 47 | Lightest text — placeholders, ultra-muted captions |

### Brand / semantic colours

| Token | Value | Uses | Primary role |
|---|---|---|---|
| `--live` | `#B02A18` | 77 | Brand red — live badges, active accents, live scores, brand wordmark |
| `--live-bg` | `rgba(176,42,24,0.07)` | 15 | Tinted red background for selected states, score chips |
| `--forest` | `#1A5C38` | 74 | Green — away/draw/QUT result pills, UKGC dot, poll indicator, offer category icons |
| `--forest-bg` | `rgba(26,92,56,0.07)` | 23 | Tinted green background for responsible gambling cards, result chips |
| `--gold` | `#8B6914` | 23 | Amber — draw result pills, counter-at-limit warning |
| `--gold-bg` | `rgba(139,105,20,0.07)` | 8 | Tinted amber background for draw chips |

### League / competition colours

| Token | Value | Uses | Primary role |
|---|---|---|---|
| `--pl` | `#38003C` | 0 | Premier League purple (defined but never used via var(); applied inline in LEAGUE_INFO) |
| `--ucl` | `#003087` | 5 | UEFA Champions League blue |
| `--racing` | `#1A4D2E` | 3 | Racing green — used on OH-hero card button |
| `--pitch` | `#091522` | 4 | Very dark blue-black — match header dark background |

### Borders / dividers

| Token | Value | Uses | Primary role |
|---|---|---|---|
| `--rule` | `rgba(26,23,20,0.09)` | 86 | Default separator — between rows, inside cards |
| `--rule-strong` | `rgba(26,23,20,0.16)` | 42 | Stronger separator — panel edges, input borders |

### Typography (font stacks)

| Token | Value | Uses | Primary role |
|---|---|---|---|
| `--fd` | `'Playfair Display', Georgia, serif` | 26 | Display/decorative — wordmark, screen headers, hero scores |
| `--fs` | `'Instrument Sans', system-ui, sans-serif` | 119 | Body text — the workhorse sans-serif |
| `--fm` | `'IBM Plex Mono', monospace` | 137 | Monospaced — scores, odds, times, badges, labels |

---

## Notes for migration

### Token naming conventions (existing vs incoming v1.0)

The existing tokens use short, role-suggestive names (`--ink`, `--parchment`, `--live`) rather than semantic ones. The v1.0 system uses fully semantic names (`--text-primary`, `--bg-surface`, `--brand-red`). There are **zero name collisions** — they can coexist in `:root` without any conflict.

### Mapping sketch (not prescriptive — for reference only)

| Existing token | Nearest v1.0 equivalent | Notes |
|---|---|---|
| `--parchment` | `--bg-primary` | v1.0 is dark-mode; parchment is light — not a direct swap |
| `--card` | `--bg-surface` | Similar elevation role, opposite colour |
| `--ink` | `--text-primary` | Inverted — ink is near-black, v1.0 text-primary is off-white |
| `--ink4` | `--text-muted` | Close semantic match |
| `--live` | `--brand-red` | `#B02A18` vs `#C8302C` — slightly different reds |
| `--rule` | `--border-subtle` | Both low-contrast separators |
| `--rule-strong` | `--border-medium` | Similar strength |
| `--forest` | `--success` | `#1A5C38` vs `#4A7C59` — different greens |
| `--gold` | `--warning` | `#8B6914` vs `#C99A2E` — different ambers |
| `--fs` | `--font-sans` | Different font choices (Instrument Sans vs Inter) |
| `--fd` | `--font-serif` | Different font choices (Playfair vs Source Serif Pro) |
| `--fm` | `--font-mono` | Different font choices (IBM Plex Mono vs JetBrains Mono) |

### Usage outliers worth noting

- `--ink` (225 uses) and `--rule` (86 uses) are the most-used tokens — any future migration touching these should be done in a dedicated, heavily-reviewed batch.
- `--pl` (0 uses via `var()`) — the Premier League purple is applied via hardcoded hex in `LEAGUE_INFO` inline styles rather than via the token.
- `--ink2` (1 use) — effectively redundant; the single use could migrate to `--ink3` without visible change.

---

*24 tokens inventoried · 0 name conflicts with v1.0 design tokens · April 2026*
