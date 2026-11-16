# Live relay for the lower leagues

The bet tracker gets live football scores from ESPN, which has no National
League North/South or Scottish League One/Two. LiveScore has all four (live
score, minute and half-time score), but it refuses requests made from a web
page, so the tracker can't read it directly.

`lower-leagues-worker.js` is a small relay that runs on Cloudflare's free
Workers plan. It fetches LiveScore from Cloudflare's servers, keeps only those
four leagues, and lets only the tracker's site read the answer. Each date is
cached for 30 seconds, so LiveScore sees at most two requests a minute however
often the page refreshes. The free plan allows 100,000 requests a day; a busy
Saturday uses a few hundred.

## Setting it up from GitHub (no pasting; best on a phone)

1. Sign up at <https://dash.cloudflare.com/sign-up> (free, no card).
2. Menu -> **Compute** -> **Workers & Pages** -> **Create** -> **Import a
   repository** (or "Continue with GitHub"). Connect GitHub and allow access
   to `Pitchside-App26/pitchside-backend`.
3. Pick that repository. In the setup screen:
   - Project name: `pitchside-live`
   - Root directory (under Advanced / Build settings): `relay`
   - Deploy command: `npx wrangler deploy` (usually filled in already)
   - Build command: leave empty
   - Build watch paths, if offered: `relay/*`, so only changes to the relay
     redeploy it.
   Tap **Create and deploy** / **Deploy**.
4. Check and send the address as in steps 4-5 below.

## Setting it up by pasting (easier on a computer)

1. **Sign up.** Go to <https://dash.cloudflare.com/sign-up> and create a free
   account (email and password; no card needed). Verify the email.
2. **Create the Worker.** In the dashboard open **Workers & Pages**, tap
   **Create**, then **Create Worker** (or "Start with Hello World!").
   Name it `pitchside-live` and tap **Deploy**.
3. **Paste the code.** Tap **Edit code**. Select everything in the editor and
   delete it. Open
   <https://raw.githubusercontent.com/Pitchside-App26/pitchside-backend/main/relay/lower-leagues-worker.js>,
   select all, copy, paste it into the editor, and tap **Deploy**.
4. **Check it.** Open your Worker's address with a date on the end, e.g.
   `https://pitchside-live.<your-name>.workers.dev/?date=20261114`. You should
   see the day's matches as text, starting `{"date":"20261114","matches":[`.
   (Scottish League One and Two that Saturday: Airdrieonians 2-0 Queen of the
   South, and so on.) If it says `LiveScore answered 403`, LiveScore is
   blocking Cloudflare: tell Claude, and we'll try another route.
5. **Send the address** (`https://pitchside-live.<your-name>.workers.dev`) to
   Claude. It goes into `LOWER_LEAGUE_RELAY` in
   `nfl_prop_engine/site/tracker.html`, and from then on legs in those four
   leagues are followed live on the tracker, half-time scores included.

## Notes

- The relay only ever answers the tracker's site
  (`https://pitchside-app26.github.io`); other websites can't use it.
- If LiveScore changes its feed, the tracker shows those legs as "match not
  found on the live feed" rather than anything wrong. The goals report uses
  the same feed for grading (`football_goals/sources/livescore.py`), so a
  change would show up there too.
- To change the code later, edit it in the Cloudflare dashboard the same way
  (Edit code, paste, Deploy). The address stays the same.
