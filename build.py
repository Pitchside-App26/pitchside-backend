#!/usr/bin/env python3
"""
build.py — Phase A assembly script
Reads rundown-base.html and inserts all Phase A additions
to produce rundown-phase-a.html
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
print("  Phase A build")
print("=" * 52)

# ── 1. Read source files ──────────────────────────────
print("\n[1] Reading source files…")
base       = read('rundown-base.html')
styles     = read('phase-a-styles.css')
screens    = read('phase-a-screens.html')
js1        = read('phase-a-additions.js')
js2        = read('phase-a-additions-2.js')
print("  ✓  All source files found")

html = base

# ── 2. Insert CSS before </style> (first occurrence) ─
print("\n[2] Inserting phase-a-styles.css before </style>…")
css_block = '\n/* ── phase-a-styles.css ── */\n' + styles
html = insert_before_first(html, '</style>', css_block,
                           'CSS inserted before first </style>')

# ── 3. Insert Supabase CDN in <head> before </head> ──
print("\n[3] Inserting Supabase CDN script tag before </head>…")
cdn = '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>'
html = insert_before_first(html, '</head>', cdn,
                           'Supabase CDN tag inserted before </head>')

# ── 4. Insert new screen HTML fragments ──────────────
print("\n[4] Inserting phase-a-screens.html into phone div…")
# The base file ends the phone div with </div>  (closing .phone)
# We look for the comment marker; fall back to the bare close tag
phone_marker = '</div><!-- /phone -->'
if phone_marker not in html:
    # Try bare closing div preceded by the last screen — use a safe fallback
    phone_marker = '</div>\n\n  <div id="sdesc"'
    if phone_marker not in html:
        # Last resort: just before the closing </div> of .scene
        phone_marker = '\n  </div><!-- /phone -->'

if phone_marker in html:
    html = insert_before_first(html, phone_marker, screens,
                               'Screen fragments inserted before phone close')
else:
    # Manual fallback: inject after last </div> before </div class="scene">
    # Find the last screen div and insert after it
    last_screen = html.rfind('</div>\n\n  <div id="sdesc"')
    if last_screen == -1:
        last_screen = html.rfind('<div id="sdesc"')
    if last_screen == -1:
        print("  ✗  MARKER NOT FOUND: phone close div")
        sys.exit(1)
    html = html[:last_screen] + screens + '\n\n  ' + html[last_screen:]
    print("  ✓  Screen fragments inserted (fallback)")

# ── 5 & 6. Append both JS files before last </script>
print("\n[5/6] Inserting JS files before last </script>…")
js_block = (
    '\n\n/* ── phase-a-additions.js ── */\n' + js1 +
    '\n\n/* ── phase-a-additions-2.js ── */\n' + js2
)
html = insert_before(html, '</script>', js_block,
                     'Both JS files inserted before last </script>')

# ── 7. Write output ───────────────────────────────────
print("\n[7] Writing rundown-phase-a.html…")
out_path = os.path.join(BASE_DIR, 'rundown-phase-a.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

# ── 8. Confirmation stats ─────────────────────────────
size_kb = os.path.getsize(out_path) / 1024
lines   = html.count('\n') + 1

print("\n" + "=" * 52)
print("  BUILD COMPLETE")
print("=" * 52)
print(f"  Output : rundown-phase-a.html")
print(f"  Size   : {size_kb:.1f} KB")
print(f"  Lines  : {lines:,}")
print("=" * 52)
