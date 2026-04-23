# Cleanup Report — Section G: Potentially Stale Files

---

## G1. `rundown-phase-a.html` — superseded build artifact

**Size:** ~215 KB, 3,827 lines
**Last modified:** April 17 2026 (same day as current build)
**Tracked in git:** Yes

This is the output of a prior build phase (Phase A only, before Phase B and NAV-1 were added). It is not referenced by `build.py`, not deployed to Netlify, and is entirely superseded by `index.html` (the current build output). It adds 215KB to the repository with no benefit.

**Verdict: Safe to delete.** The source files (`rundown-base.html` + all phase-a/b/nav-1 fragments) are the canonical inputs — the built artifact has no independent value. If a Phase A snapshot is needed for comparison, it exists in git history.

**Action:** Delete file, add `rundown-phase-*.html` to `.gitignore` to prevent future build artifacts accumulating (keep `index.html` tracked since it's the deployment target).

---

## G2. `team-ids.txt` — consumed development artifact

**Size:** ~4 KB
**Last modified:** April 17 2026
**Tracked in git:** Yes

This is the output of `fetch-team-ids.js` — a one-time script that fetched API-Football team IDs and wrote them to a text file for manual copy-paste into `phase-a-additions-2.js`. The `TEAM_IDS` object in `phase-a-additions-2.js` (lines 98–125) already contains the incorporated data. The text file has no further purpose.

**Verdict: Safe to delete.** The data it contains is already in the codebase. Add `team-ids.txt` to `.gitignore`.

---

## G3. `cleanup-report-section-a.md` — superseded by renamed file

**Size:** ~8 KB
**Tracked in git:** Yes

This was the first version of Section A, committed before the naming convention (`-dead-code` suffix) was established. `cleanup-report-section-a-dead-code.md` is the canonical version with identical content. The original is redundant.

**Verdict: Safe to delete** once the cleanup report series is complete.

---

## G4. `app/` — empty directory

**Tracked in git:** Only as an empty directory placeholder (no files inside)

The `app/` directory contains nothing. Git does not track empty directories natively — it exists only because a `.gitkeep` or similar placeholder was once present, or it was created locally and never populated. It has no purpose in the current project structure.

**Verdict: Safe to delete.**

---

## G5. `fetch-team-ids.js` — one-time utility, no longer needed

**Size:** ~3 KB
**Tracked in git:** Yes

A Node.js script used once to fetch team IDs from API-Football and write `team-ids.txt`. The data has been incorporated into `phase-a-additions-2.js`. The script will need updating every summer when promotions/relegations change team memberships — at which point it would be run again, results checked, and `TEAM_IDS` updated manually.

**Verdict: MEDIUM confidence.** Not stale in the sense that it may be needed again next summer. However, it is a development utility that doesn't belong in the root of a production repository. Options:
- Move to a `scripts/` or `tools/` subdirectory
- Add a comment to the file noting when it was last run and what output it produced
- Keep as-is (lowest risk)

Do not delete without confirming the team-ID update process is documented elsewhere.

---

## G6. `rundown-phase-b.html` — duplicate of `index.html`

**Size:** ~238 KB
**Tracked in git:** Yes

`rundown-phase-b.html` is the direct output of `build.py`. `index.html` is a copy of it (produced by `cp rundown-phase-b.html index.html` in the deploy workflow). Both files are currently identical except for the first line cache-buster comment. Tracking both in git means every build commit adds ~476KB of near-identical content.

**Verdict: MEDIUM confidence.** The separation exists because `build.py` writes `rundown-phase-b.html` by name and then the deploy step copies it to `index.html`. Simplest fix: change `build.py` to write `index.html` directly, eliminating `rundown-phase-b.html` entirely. Risk: low — build.py's output path is a one-line change.

---

## G7. `api/sync.js` — may never have run successfully

As identified in Section D4, `api/sync.js` has a CJS/ESM module mismatch (`export default` + `require()`). Combined with the `versel.json` typo (Section D3), this function has likely never been triggered by Vercel cron in production.

**Verdict: Not stale per se, but effectively dormant.** Both issues are fixable (rename config file, fix module export). The `matches` table in Supabase may be empty or stale as a result. Worth verifying the table state before assuming fixture data is current.

---

*End of Section G. 7 items reviewed — 3 safe to delete, 2 medium confidence, 1 simplification opportunity, 1 dormant backend function.*
