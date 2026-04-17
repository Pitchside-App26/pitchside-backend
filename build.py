#!/usr/bin/env python3
"""
build.py — Phase B + NAV-1 assembly script
Reads rundown-base.html and inserts all Phase A, Phase B, and NAV-1 additions
to produce rundown-phase-b.html
"""

import os, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def read(filename):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        print(f"  ✗  MISSING: {filename}")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def insert_before(html, marker, content, label):
    if marker not in html:
        print(f"  ✗  MARKER NOT FOUND: '{marker}' ({label})")
        sys.exit(1)
    # Insert once — at the LAST occurrence (safest for </script>)
    idx = html.rfind(marker)
    result = html[:idx] + content + '\n' + html[idx:]
    print(f"  ✓  {label}")
    return result

def insert_before_first(html, marker, content, label):
    """Insert before the FIRST occurrence of marker."""
    if marker not in html:
        print(f"  ✗  MARKER NOT FOUND: '{marker}' ({label})")
        sys.exit(1)
    idx = html.index(marker)
    result = html[:idx] + content + '\n' + html[idx:]
    print(f"  ✓  {label}")
    return result

print("=" * 52)
print("  Phase B + NAV-1 build")
print("=" * 52)

# ── 1. Read source files ──────────────────────────────
print("\n[1] Reading source files…")
base       = read('rundown-base.html')
styles_a   = read('phase-a-styles.css')
styles_b   = read('phase-b-styles.css')
styles_nav = read('nav-1-styles.css')
screens    = read('phase-a-screens.html')
js1        = read('phase-a-additions.js')
js2        = read('phase-a-additions-2.js')
js3        = read('phase-b-scripts.js')
js4        = read('nav-1-scripts.js')
print("  ✓  All source files found")

html = base

# ── 2. Insert CSS before </style> (first occurrence) ─
print("\n[2] Inserting CSS files before </style>…")
css_block = (
    '\n/* ── phase-a-styles.css ── */\n' + styles_a +
    '\n/* ── phase-b-styles.css ── */\n' + styles_b +
    '\n/* ── nav-1-styles.css ── */\n'   + styles_nav
)
html = insert_before_first(html, '</style>', css_block,
                           'phase-a + phase-b + nav-1 styles inserted before first </style>')

# ── 3. Insert Supabase CDN in <head> before </head> ──
print("\n[3] Inserting Supabase CDN script tag before </head>…")
cdn = '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>'
html = insert_before_first(html, '</head>', cdn,
                           'Supabase CDN tag inserted before </head>')

# ── 4. Insert new screen HTML fragments ──────────────
print("\n[4] Inserting phase-a-screens.html into phone div…")
phone_marker = '</div><!-- /phone -->'
if phone_marker not in html:
    phone_marker = '</div>\n\n  <div id="sdesc"'
    if phone_marker not in html:
        phone_marker = '\n  </div><!-- /phone -->'

if phone_marker in html:
    html = insert_before_first(html, phone_marker, screens,
                               'Screen fragments inserted before phone close')
else:
    last_screen = html.rfind('</div>\n\n  <div id="sdesc"')
    if last_screen == -1:
        last_screen = html.rfind('<div id="sdesc"')
    if last_screen == -1:
        print("  ✗  MARKER NOT FOUND: phone close div")
        sys.exit(1)
    html = html[:last_screen] + screens + '\n\n  ' + html[last_screen:]
    print("  ✓  Screen fragments inserted (fallback)")

# ── 5/6/7/8. Append all JS files before last </script> ─
print("\n[5/6/7/8] Inserting JS files before last </script>…")
js_block = (
    '\n\n/* ── phase-a-additions.js ── */\n' + js1 +
    '\n\n/* ── phase-a-additions-2.js ── */\n' + js2 +
    '\n\n/* ── phase-b-scripts.js ── */\n' + js3 +
    '\n\n/* ── nav-1-scripts.js ── */\n' + js4
)
html = insert_before(html, '</script>', js_block,
                     'phase-a + phase-a-2 + phase-b + nav-1 JS inserted before last </script>')

# ── 8. Write output ───────────────────────────────────
print("\n[8] Writing rundown-phase-b.html…")
out_path = os.path.join(BASE_DIR, 'rundown-phase-b.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

# ── 9. Confirmation stats ─────────────────────────────
size_kb = os.path.getsize(out_path) / 1024
lines   = html.count('\n') + 1

print("\n" + "=" * 52)
print("  BUILD COMPLETE")
print("=" * 52)
print(f"  Output : rundown-phase-b.html")
print(f"  Size   : {size_kb:.1f} KB")
print(f"  Lines  : {lines:,}")
print("=" * 52)

# ── 10. Content checks ────────────────────────────────
print("\n[10] Content checks…")
checks = [
    ('MOCK_ODDS',                   'MOCK_ODDS array present'),
    ('AFFILIATE_URLS',              'AFFILIATE_URLS present'),
    ('id="market-tabs"',            'market-tabs element present'),
    ('id="offer-cards-container"',  'offer-cards-container element present'),
    ('id="odds-comparison-rows"',   'odds-comparison-rows element present'),
    ('id="featured-offer-container"', 'featured-offer-container element present'),
    ('betting-compliance-strip',    'compliance strips present'),
    ('class="rundown-nav"',         'shared bottom nav bar present'),
    ('NAV_TAB_MAP',                 'NAV_TAB_MAP present'),
    ('data-tab="matchday"',         'Match Day tab present'),
]
all_ok = True
for needle, label in checks:
    if needle in html:
        print(f"  ✓  {label}")
    else:
        print(f"  ✗  MISSING: {label}")
        all_ok = False

print("\n" + ("  All checks passed." if all_ok else "  ✗ Some checks FAILED."))
print("=" * 52)
