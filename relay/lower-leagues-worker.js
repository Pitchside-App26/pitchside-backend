// Pitchside live relay: a Cloudflare Worker (free plan) that passes LiveScore's
// live scores for the four leagues ESPN doesn't cover to the bet tracker.
//
//   GET https://<your-worker>.workers.dev/?date=20261114
//   -> { "date": "20261114", "matches": [ { league, id, home, away, status, kickoff,
//        homeGoals, awayGoals, homeHT, awayHT, homeFT90, awayFT90 } ] }
//
// LiveScore refuses requests made from a web page, so the tracker can't call
// it directly; this Worker calls it from Cloudflare's servers instead, keeps
// only the four leagues, and lets the tracker's site (and nobody else's) read
// the answer. Each date is cached for 30 seconds, so however often the page
// refreshes, LiveScore sees at most two requests a minute.
//
// Setup: see relay/README.md. Cloudflare rebuilds the Worker from this folder
// whenever it changes on main; no pasting needed.

const ALLOWED_ORIGIN = "https://pitchside-app26.github.io";
const CACHE_SECONDS = 30;
const LEAGUES = {
  "England|National League: North": "north",
  "England|National League: South": "south",
  "Scotland|League 1": "sco3",
  "Scotland|League 2": "sco4",
};

export function pickMatches(feed) {
  const num = v => (/^\d+$/.test(String(v ?? "").trim()) ? Number(v) : null);
  const out = [];
  for (const stage of (feed && feed.Stages) || []) {
    const league = LEAGUES[`${stage.Cnm}|${stage.Snm}`];
    if (!league) continue;
    for (const e of stage.Events || []) {
      out.push({
        league,
        id: String(e.Eid),
        home: ((e.T1 || [])[0] || {}).Nm || "",
        away: ((e.T2 || [])[0] || {}).Nm || "",
        status: String(e.Eps ?? ""),          // "NS", "15:00", "23'", "HT", "FT", "AET", "Postp." ...
        kickoff: String(e.Esd ?? ""),         // YYYYMMDDhhmmss, UTC
        homeGoals: num(e.Tr1), awayGoals: num(e.Tr2),
        homeHT: num(e.Trh1), awayHT: num(e.Trh2),
        homeFT90: num(e.Tr1OR), awayFT90: num(e.Tr2OR),  // 90-minute score, when a match went to extra time
      });
    }
  }
  return out;
}

function respond(body, status, origin) {
  const headers = { "content-type": "application/json; charset=utf-8", "cache-control": `max-age=${CACHE_SECONDS}` };
  if (origin === ALLOWED_ORIGIN) {
    headers["access-control-allow-origin"] = ALLOWED_ORIGIN;
    headers["vary"] = "Origin";
  }
  return new Response(JSON.stringify(body), { status, headers });
}

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin");
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: origin === ALLOWED_ORIGIN ? {
        "access-control-allow-origin": ALLOWED_ORIGIN, "access-control-allow-methods": "GET", "vary": "Origin" } : {} });
    }
    if (request.method !== "GET") return respond({ error: "GET only" }, 405, origin);

    const date = new URL(request.url).searchParams.get("date") || "";
    if (!/^\d{8}$/.test(date)) return respond({ error: "add ?date=YYYYMMDD" }, 400, origin);

    // One LiveScore request per date per 30 seconds, whoever is asking.
    const cacheKey = new Request(`https://relay.cache/${date}`);
    const cache = caches.default;
    let body = await (await cache.match(cacheKey))?.json?.();
    if (!body) {
      const upstream = await fetch(`https://prod-public-api.livescore.com/v1/api/app/date/soccer/${date}/0`, {
        headers: { "accept": "application/json", "user-agent": "Mozilla/5.0 (pitchside bet tracker relay)" },
      });
      if (!upstream.ok) return respond({ error: `LiveScore answered ${upstream.status}` }, 502, origin);
      body = { date, fetched: new Date().toISOString(), matches: pickMatches(await upstream.json()) };
      ctx.waitUntil(cache.put(cacheKey, new Response(JSON.stringify(body), {
        headers: { "cache-control": `max-age=${CACHE_SECONDS}` } })));
    }
    return respond(body, 200, origin);
  },
};
