# Cleanup Report — Section D: Security & Config Issues

---

## D1. Hardcoded Supabase credentials in `phase-a-additions.js` — lines 18–19

```js
// Hardcoded fallbacks for testing — remove before production
const SUPABASE_URL = 'https://vmwcumegngppqojetfvv.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZtd2N1bWVnbmdwcHFvamV0ZnZ2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU3MjUxMzEsImV4cCI6MjA5MTMwMTEzMX0.H6KkZzjI_iShy6pr7AVCgWQi9TTzNL9qtkViL8dOw9I';
```

**Severity: MEDIUM.** The `anon` (public) key is intentionally designed to be exposed in client-side code — it is not a secret. Supabase's security model relies on Row Level Security policies, not key secrecy, for the anon role. However:

- The URL and key are committed to git history and will remain there permanently even after removal
- The key has a very long expiry (decoded: `exp: 2091-03-01`) — it will be valid for 65+ years
- The comment "remove before production" has not been acted on
- Because they're in a client-side JS file, they're visible to anyone who views source on the deployed app regardless

**What to do:**
1. Keep using these values as the fallback (they're public-safe for anon role)
2. Remove the `// Hardcoded fallbacks for testing — remove before production` comment and replace with `// Public anon key — safe for client-side use. RLS policies enforce access control.`
3. Verify RLS is enabled on all tables (see D5)

**What NOT to do:** Do not commit the `SUPABASE_SERVICE_ROLE_KEY` (used in `api/sync.js` via environment variable) to any client-side file. That key bypasses RLS entirely.

---

## D2. No `.gitignore` file

**Severity: MEDIUM.** There is no `.gitignore` in the repository root. This means:
- Any `.env` file added locally will be committed
- `node_modules/` (if `npm install` is run locally) will be committed
- OS files (`.DS_Store`, `Thumbs.db`) will be committed
- Editor config files will be committed
- Future build artifacts will accumulate

**Recommended `.gitignore` for this project:**
```
node_modules/
.env
.env.local
.DS_Store
Thumbs.db
*.log
```
The existing tracked artifacts (`rundown-phase-a.html`, `team-ids.txt`) should also be assessed for removal (see Section G).

---

## D3. `versel.json` — typo prevents cron from running

**File:** `versel.json` (should be `vercel.json`)

**Severity: HIGH (functional bug, not security).** Vercel reads `vercel.json` for project configuration. The file is named `versel.json` and will be silently ignored. This means:

- The `/api/sync` cron job (every 30 minutes) is **not registered** with Vercel
- Match data is not being synced to Supabase on any schedule
- No error is thrown — Vercel simply uses default configuration

**Fix:** Rename `versel.json` → `vercel.json`.

---

## D4. `api/sync.js` — CJS/ESM module syntax mismatch

**Severity: HIGH (runtime bug).** The file mixes module systems:
```js
const { createClient } = require('@supabase/supabase-js');  // CommonJS
const axios = require('axios');                              // CommonJS
...
export default async function handler(req, res) { ... }     // ESM — incompatible
```

Node.js cannot run a file with both `require()` and `export default`. Vercel serverless functions use CommonJS by default (unless `"type": "module"` is in `package.json`, which it isn't).

**Fix:** Replace `export default` with `module.exports =`:
```js
module.exports = async function handler(req, res) { ... }
```

**Additional issue:** `package.json` has no `"type"` field, confirming CommonJS mode is expected.

---

## D5. `package.json` — dependency versions pinned to `"latest"`

```json
"dependencies": {
  "@supabase/supabase-js": "latest",
  "axios": "latest"
}
```

**Severity: LOW-MEDIUM.** Using `"latest"` means `npm install` will always pull the newest version. This is an anti-pattern because:
- A breaking major version of either package will silently break `api/sync.js` on next deploy
- The Supabase JS SDK has had breaking changes between v1, v2, and v3
- `axios` has had breaking changes between v0.x and v1.x

**Fix:** Pin to specific versions, e.g.:
```json
"@supabase/supabase-js": "^2.49.0",
"axios": "^1.7.0"
```

---

## D6. `localStorage` used for Supabase credentials entered via Profile

In `phase-a-additions.js` `saveSupabaseCredentials()` (line 274):
```js
localStorage.setItem('sb_url', url.trim());
localStorage.setItem('sb_key', key.trim());
```

And in `initSupabase()` (line 21):
```js
var url = localStorage.getItem('sb_url') || SUPABASE_URL;
var key = localStorage.getItem('sb_key') || SUPABASE_KEY;
```

**Severity: LOW.** The `sb_key` stored is the Supabase anon key, which is public-safe (see D1). Storing it in `localStorage` is acceptable. However, the connection card in the Profile screen asks users to paste their "anon public key" — if a user accidentally pastes their `service_role` key instead, it would be stored in `localStorage` and exposed to any JS running on the page (including injected scripts via XSS). No active XSS vector exists currently, but worth noting.

**Recommendation:** Add a label in the connection card UI: "Anon (public) key only — never enter your service role key here."

---

## D7. AFFILIATE_URLS are placeholder homepage URLs, not tracked affiliate links

```js
// TODO Gate 2: replace all values with real tracked affiliate URLs before going live
var AFFILIATE_URLS = {
  'Bet365': 'https://www.bet365.com/',
  ...
};
```

**Severity: LOW (commercial risk, not security).** The current URLs link directly to bookmaker homepages without affiliate tracking parameters. Until Gate 2, no revenue is generated from referral clicks. Not a security issue, but a commercial one. The TODO comment is correctly placed.

---

## D8. Supabase RLS — cannot verify without database access

The following tables are referenced in application code and should have RLS enabled:

| Table | Used in | Expected policies |
|---|---|---|
| `user_profiles` | `phase-a-additions.js` | Users can only read/write their own row (`auth.uid() = id`) |
| `pitchside_offers` | `phase-b-scripts.js` | Public read for active offers; no user write |
| `matches` | `api/sync.js` | Public read; service role write only |

**Cannot verify** without Supabase dashboard access. If RLS is not enabled on `user_profiles`, any authenticated user could read or overwrite another user's profile data. This should be confirmed before launch.

**Recommended check:** In Supabase dashboard → Table Editor → each table → RLS tab. Confirm `is_rls_enabled = true` and that policies exist for each operation used by the app.

---

*End of Section D. 8 security/config issues identified (2 HIGH, 3 MEDIUM, 3 LOW).*
