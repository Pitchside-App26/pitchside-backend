/* Live bet tracker: the pure logic, shared by tracker.html and the Node
   tests (tests/tracker-core.test.js). Reads ESPN's public NFL scoreboard and
   game summary JSON (no key; the API allows cross-origin requests) and works
   out where each leg of each bet stands.

   A bet: { id, book, kind, odds, stake, returns, placed, legs: [leg] }.
   A leg is one of:
     { type: "moneyline", game: "KC@ATL", team: "KC" }
     { type: "total", game: "HOU@CLE", side: "over"|"under", line: 41 }
     { type: "player", game: "SF@DAL", player: "Brock Purdy", stat: "passingYards", side: "over"|"under", line: 260.5 }
     { type: "anytime_td", game: "SF@DAL", player: "Christian McCaffrey" }
     { type: "other", label: "...", note: "can't be followed live" }  (spreads, first TD, ...)
   game is ESPN's "AWAY@HOME" abbreviations (Rams LAR, Commanders WSH).
*/
(function (root) {
  "use strict";

  const STATS = {
    passingYards: { cat: "passing", key: "passingYards", label: "pass yds" },
    completions: { cat: "passing", key: "completions/passingAttempts", part: 0, label: "completions" },
    passingTouchdowns: { cat: "passing", key: "passingTouchdowns", label: "pass TDs" },
    interceptions: { cat: "passing", key: "interceptions", label: "INTs" },
    rushingYards: { cat: "rushing", key: "rushingYards", label: "rush yds" },
    carries: { cat: "rushing", key: "rushingAttempts", label: "carries" },
    receivingYards: { cat: "receiving", key: "receivingYards", label: "rec yds" },
    receptions: { cat: "receiving", key: "receptions", label: "receptions" },
    tackles: { cat: "defensive", key: "totalTackles", label: "tackles" },
    sacks: { cat: "defensive", key: "sacks", label: "sacks" },
  };
  // Anytime TD scorer: rushing, receiving and return touchdowns (not passing).
  const TD_SOURCES = [
    ["rushing", "rushingTouchdowns"], ["receiving", "receivingTouchdowns"],
    ["kickReturns", "kickReturnTouchdowns"], ["puntReturns", "puntReturnTouchdowns"],
    ["interceptions", "interceptionTouchdowns"], ["defensive", "defensiveTouchdowns"],
  ];

  function nameKey(name) {
    return String(name || "").toLowerCase()
      .replace(/\b(jr|sr|ii|iii|iv|v)\b\.?/g, "")
      .replace(/[^a-z ]/g, "").replace(/\s+/g, " ").trim();
  }

  // ── Scoreboard ──
  function parseScoreboard(json) {
    const games = {};
    for (const event of (json && json.events) || []) {
      const comp = (event.competitions || [])[0] || {};
      const side = {};
      for (const c of comp.competitors || []) {
        side[c.homeAway] = { team: c.team && c.team.abbreviation, score: Number(c.score) || 0 };
      }
      if (!side.home || !side.away) continue;
      const status = event.status || comp.status || {};
      const type = status.type || {};
      const key = `${side.away.team}@${side.home.team}`;
      games[key] = {
        id: event.id, key, away: side.away, home: side.home,
        state: type.state || "pre",  // "pre" | "in" | "post"
        final: type.state === "post" && type.completed !== false,
        detail: type.shortDetail || type.detail || "",
        period: status.period || 0, clock: status.displayClock || "",
      };
    }
    return games;
  }

  // ── Box score ──
  // { "brock purdy": { name, team, cats: { passing: { passingYards: 59, ... } } } }
  function parseBoxscore(summary) {
    const players = {};
    for (const team of ((summary && summary.boxscore && summary.boxscore.players) || [])) {
      const abbr = team.team && team.team.abbreviation;
      for (const cat of team.statistics || []) {
        const keys = cat.keys || [];
        for (const row of cat.athletes || []) {
          const name = row.athlete && row.athlete.displayName;
          if (!name) continue;
          const id = nameKey(name);
          const p = players[id] || (players[id] = { name, team: abbr, cats: {} });
          const values = {};
          keys.forEach((k, i) => { values[k] = (row.stats || [])[i]; });
          p.cats[cat.name] = values;
        }
      }
    }
    return players;
  }

  // "C. McCaffrey" / "J. Williams" / "Christian McCaffrey" -> the box-score player.
  function findPlayer(players, wanted) {
    const key = nameKey(wanted);
    if (players[key]) return players[key];
    const parts = key.split(" ");
    const last = parts[parts.length - 1];
    const initial = parts.length > 1 ? parts[0][0] : null;
    const matches = Object.keys(players).filter(k => {
      const ps = k.split(" ");
      return ps[ps.length - 1] === last && (!initial || ps[0][0] === initial);
    });
    return matches.length === 1 ? players[matches[0]] : null;
  }

  function statValue(player, stat) {
    const spec = STATS[stat];
    if (!player || !spec) return 0;
    const raw = (player.cats[spec.cat] || {})[spec.key];
    if (raw === undefined || raw === null || raw === "") return 0;
    const text = String(raw);
    const n = spec.part !== undefined ? Number(text.split(/[\/-]/)[spec.part]) : Number(text);
    return Number.isFinite(n) ? n : 0;
  }

  function touchdowns(player) {
    if (!player) return 0;
    return TD_SOURCES.reduce((sum, [cat, key]) => sum + (Number((player.cats[cat] || {})[key]) || 0), 0);
  }

  // ── Legs ──
  // status: "won" | "lost" | "void" | "winning" | "losing" | "pending" | "unknown"
  function overUnder(side, value, line, final) {
    if (side === "under") {
      if (value > line) return "lost";
      if (final) return value === line ? "void" : "won";
      return "winning";
    }
    if (value > line) return "won";
    if (final) return value === line ? "void" : "lost";
    return "losing";
  }

  function evaluateLeg(leg, games, boxscores) {
    if (leg.type === "other") return { game: games[leg.game], status: "unknown", note: leg.note || "can't be followed live" };
    const game = games[leg.game];
    if (!game) return { status: "unknown", note: `${leg.game} isn't on the scoreboard` };
    const base = { game };
    if (game.state === "pre") return { ...base, status: "pending", value: leg.type === "total" ? 0 : null };
    const final = game.final;

    if (leg.type === "moneyline") {
      const mine = game.home.team === leg.team ? game.home.score : game.away.score;
      const theirs = game.home.team === leg.team ? game.away.score : game.home.score;
      if (final) return { ...base, status: mine > theirs ? "won" : mine === theirs ? "void" : "lost", value: mine - theirs };
      return { ...base, status: mine > theirs ? "winning" : "losing", value: mine - theirs };
    }
    if (leg.type === "total") {
      const value = game.home.score + game.away.score;
      return { ...base, status: overUnder(leg.side, value, leg.line, final), value };
    }
    const box = boxscores[game.id];
    if (!box) return { ...base, status: "unknown", note: "box score not loaded yet" };
    const player = findPlayer(box, leg.player);
    if (leg.type === "anytime_td") {
      const tds = touchdowns(player);
      return { ...base, player, value: tds, status: tds > 0 ? "won" : final ? "lost" : "losing",
        note: player ? "" : "no stats yet" };
    }
    if (leg.type === "player") {
      // Not in the box score yet means he hasn't recorded the stat: 0 so far.
      const value = statValue(player, leg.stat);
      const out = { ...base, player, value, status: overUnder(leg.side, value, leg.line, final),
        note: player ? "" : (final ? "not in the box score (did he play?)" : "no stats yet") };
      return out;
    }
    return { ...base, status: "unknown", note: `unknown leg type ${leg.type}` };
  }

  // soccer(leg) -> the leg's result, for football legs (the page looks up
  // their matches); NFL legs use games and boxscores.
  function evaluateBet(bet, games, boxscores, soccer) {
    const legs = bet.legs.map(leg => ({ leg, ...(leg.sport === "soccer" && soccer ? soccer(leg) : evaluateLeg(leg, games, boxscores)) }));
    const counts = s => legs.filter(l => l.status === s).length;
    const settled = l => l.status === "won" || l.status === "void";
    let status;
    if (counts("lost")) status = "lost";
    else if (legs.every(settled)) status = "won";
    // Everything the tracker can follow has landed; the rest is down to you.
    else if (legs.every(l => settled(l) || l.leg.type === "other")) status = "check";
    else if (legs.some(l => (l.game && l.game.state === "in") || (l.match && l.match.state === "in"))) status = "live";
    else status = legs.some(l => l.status === "won") ? "live" : "pending";
    return { bet, legs, status, won: counts("won"), lost: counts("lost"), total: legs.length };
  }

  // What a leg needs, in words: "needs 82 more", "1 more TD", "lead by 7".
  function progressText(leg, result) {
    const v = result.value;
    if (v === null || v === undefined) return "";
    if (leg.type === "moneyline") return v === 0 ? "level" : v > 0 ? `leading by ${v}` : `trailing by ${-v}`;
    if (leg.type === "anytime_td") return v > 0 ? `${v} TD` : "no TD yet";
    if (leg.side === "under") return v > leg.line ? "gone over" : `${fmt(leg.line - v)} to spare`;
    return v > leg.line ? "landed" : `needs ${fmt(Math.floor(leg.line) + 1 - v)} more`;
  }

  function fmt(n) {
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
  }

  // ════════════════════════ Football (soccer) ════════════════════════
  // Legs: { sport: "soccer", league: "eng.3" | null, date: "YYYYMMDD", home, away, type, ... }
  //   type "goals":  side "over"|"under", line (match goals, 90 minutes)
  //   type "btts":   side "yes"|"no"
  //   type "result": pick "home"|"draw"|"away"
  //   type "gibh":   a goal in both halves
  // league is an ESPN slug; null means "search the usual leagues".

  // The goals page's league names -> ESPN slugs. National League North/South
  // and Scottish League One/Two have no ESPN feed: they come from LiveScore
  // through the Cloudflare relay (relay/lower-leagues-worker.js), as "ls:*".
  const RELAY_LEAGUES = {
    "National League North": "ls:north", "National League South": "ls:south",
    "Scottish League One": "ls:sco3", "Scottish League Two": "ls:sco4",
  };
  const GOALS_LEAGUES = {
    "Premier League": "eng.1", "Championship": "eng.2", "League One": "eng.3", "League Two": "eng.4",
    "National League": "eng.5", "Scottish Premiership": "sco.1", "Scottish Championship": "sco.2",
  };
  const SEARCH_LEAGUES = ["eng.1", "eng.2", "eng.3", "eng.4", "eng.5", "sco.1", "sco.2", "esp.1", "ger.1", "ita.1",
    "fra.1", "ned.1", "por.1", "uefa.champions", "uefa.europa", "uefa.europa.conf", "eng.fa", "eng.league_cup"];
  const OFF = /POSTPONED|CANCEL|ABANDON|SUSPENDED|FORFEIT/;

  // Club names differ between sources ("Man Utd" / "Manchester United"); a
  // port of football_goals/names.py.
  const DROP = new Set(["fc", "afc", "the", "town", "city", "united", "utd", "athletic", "ath", "rovers", "rvs",
    "county", "harriers", "albion", "wanderers", "hotspur", "and", "&", "football", "club"]);
  const ALIASES = [["man", "manchester"], ["nottm", "nottingham"], ["sheffield weds", "sheffield wednesday"],
    ["peterboro", "peterborough"], ["inverness c", "inverness caledonian thistle"], ["mk dons", "milton keynes dons"],
    ["wolves", "wolverhampton"], ["spurs", "tottenham"], ["qpr", "queens park rangers"], ["west brom", "west bromwich"],
    ["bristol rvs", "bristol rovers"], ["hearts", "heart of midlothian"], ["st johnstone", "saint johnstone"],
    ["st mirren", "saint mirren"], ["raith rvs", "raith rovers"], ["airdrie", "airdrieonians"]];

  function clubKey(name) {
    let s = String(name || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[^a-z0-9& ]+/g, " ").replace(/\s+/g, " ").trim();
    for (const [k, v] of ALIASES) s = s.replace(new RegExp(`\\b${k}\\b`, "g"), v);
    return s;
  }
  function clubCore(name) {
    const words = clubKey(name).split(" ").filter(w => !DROP.has(w));
    return words.join(" ") || clubKey(name);
  }
  function ratio(a, b) {  // 2 x longest common subsequence / total length
    if (!a.length && !b.length) return 1;
    const dp = new Array(b.length + 1).fill(0);
    for (let i = 1; i <= a.length; i++) {
      let prev = 0;
      for (let j = 1; j <= b.length; j++) {
        const tmp = dp[j];
        dp[j] = a[i - 1] === b[j - 1] ? prev + 1 : Math.max(dp[j], dp[j - 1]);
        prev = tmp;
      }
    }
    return (2 * dp[b.length]) / (a.length + b.length);
  }
  function clubScore(a, b) {
    const na = clubKey(a), nb = clubKey(b), ca = clubCore(a), cb = clubCore(b);
    if (na === nb) return 1;
    const full = ratio(na, nb);
    if (ca === cb) return 0.9 + 0.09 * full;
    let s = ratio(ca, cb);
    if (ca.split(" ")[0] === cb.split(" ")[0]) s = Math.max(s, 0.8) + 0.1 * ratio(ca, cb);
    if (ca.includes(cb) || cb.includes(ca)) s = Math.max(s, 0.85);
    return Math.min(s, 0.99);
  }

  function parseSoccerBoard(json, slug) {
    const matches = [];
    for (const event of (json && json.events) || []) {
      const comp = (event.competitions || [])[0] || {};
      const side = {};
      for (const c of comp.competitors || []) {
        const t = c.team || {};
        side[c.homeAway] = { name: t.displayName || "", short: t.abbreviation || t.shortDisplayName || "",
          score: Number(c.score) || 0 };
      }
      if (!side.home || !side.away) continue;
      const status = event.status || {}, type = status.type || {};
      matches.push({
        id: event.id, slug, home: side.home, away: side.away,
        state: type.state || "pre", name: type.name || "", final: type.state === "post",
        off: OFF.test(type.name || ""), period: status.period || 0,
        detail: type.state === "in" ? (type.name === "STATUS_HALFTIME" ? "HT" : status.displayClock || type.shortDetail)
          : type.shortDetail || "",
      });
    }
    return matches;
  }

  // The match for (home, away): both names must clearly match, the right way round.
  function findMatch(matches, home, away) {
    let best = null;
    for (const m of matches) {
      const s = Math.min(clubScore(home, m.home.name), clubScore(away, m.away.name));
      if (s >= 0.72 && (!best || s > best.s)) best = { m, s };
    }
    return best ? best.m : null;
  }

  // [[home, away] first half, [home, away] second half] from a match summary.
  function soccerHalves(summary) {
    const comp = (((summary || {}).header || {}).competitions || [])[0] || {};
    const by = {};
    for (const c of comp.competitors || []) by[c.homeAway] = (c.linescores || []).map(l => Number(l.displayValue ?? l.value) || 0);
    if (!by.home || !by.away || !by.home.length) return null;
    return [0, 1].map(i => [by.home[i] || 0, by.away[i] || 0]);
  }

  function soccerLegNeedsSummary(leg, match) {
    return !!match && match.state !== "pre" && (leg.type === "gibh" || /AET|PEN/.test(match.name));
  }

  function evaluateSoccerLeg(leg, match, halves) {
    if (!match) return { status: "unknown", note: "match not found on the live feed" };
    const base = { match };
    if (match.off) return { ...base, status: "void", note: "postponed or abandoned" };
    if (match.state === "pre") return { ...base, status: "pending", value: null };
    // Bets settle on 90 minutes: after extra time, use the two halves.
    let h = match.home.score, a = match.away.score;
    if (/AET|PEN/.test(match.name)) {
      if (!halves) return { ...base, status: "unknown", note: "went to extra time: half scores loading" };
      h = halves[0][0] + halves[1][0]; a = halves[0][1] + halves[1][1];
    }
    const final = match.final, total = h + a;
    if (leg.type === "goals") return { ...base, value: total, status: overUnder(leg.side, total, leg.line, final) };
    if (leg.type === "btts") {
      const both = h > 0 && a > 0;
      if (leg.side === "no") return { ...base, value: total, status: both ? "lost" : final ? "won" : "winning" };
      return { ...base, value: total, status: both ? "won" : final ? "lost" : "losing" };
    }
    if (leg.type === "result") {
      const now = h > a ? "home" : h < a ? "away" : "draw";
      return { ...base, value: total, status: now === leg.pick ? (final ? "won" : "winning") : (final ? "lost" : "losing") };
    }
    if (leg.type === "gibh") {
      if (!halves) return { ...base, value: total, status: "unknown", note: "half scores loading" };
      const first = halves[0][0] + halves[0][1], second = halves[1][0] + halves[1][1];
      const firstOver = match.period >= 2 || match.name === "STATUS_HALFTIME" || final;
      let status;
      if (first > 0 && second > 0) status = "won";
      else if ((firstOver && first === 0) || (final && second === 0)) status = "lost";
      else status = first > 0 ? "winning" : "losing";
      return { ...base, value: total, halves: [first, second], status };
    }
    return { ...base, status: "unknown", note: `unknown leg type ${leg.type}` };
  }

  function soccerProgress(leg, r) {
    if (r.value === null || r.value === undefined) return "";
    if (leg.type === "goals") {
      if (leg.side === "under") return r.value > leg.line ? "gone over" : `${fmt(leg.line - r.value)} to spare`;
      const need = Math.floor(leg.line) + 1 - r.value;
      return need <= 0 ? "landed" : `needs ${need} more goal${need === 1 ? "" : "s"}`;
    }
    if (leg.type === "gibh" && r.halves) {
      const [f, s] = r.halves;
      return `1st half ${f > 0 ? "✓" : "–"} · 2nd half ${s > 0 ? "✓" : "–"}`;
    }
    return "";
  }

  // The relay's matches, in parseSoccerBoard's shape, with the half scores
  // attached (LiveScore sends them with the score, so no summary is needed).
  const LS_DONE = new Set(["FT", "AET", "AP"]);
  function relayState(status) {
    const s = String(status || "").trim();
    if (/post|canc|aband|susp|award|int/i.test(s)) return { state: "post", off: true };
    if (LS_DONE.has(s)) return { state: "post", off: false };
    if (!s || s === "NS" || /^\d{1,2}:\d{2}$/.test(s)) return { state: "pre", off: false };
    return { state: "in", off: false };  // "23'", "45+2'", "HT", "ET" ...
  }
  function parseRelay(json) {
    const matches = [];
    for (const r of (json && json.matches) || []) {
      const { state, off } = relayState(r.status);
      const minute = parseInt(r.status, 10);
      const period = r.status === "HT" ? 1 : state === "post" || minute > 45 ? 2 : 1;
      const short = n => String(n || "").replace(/[^A-Za-z ]/g, "").slice(0, 3).toUpperCase();
      // 90-minute score: after extra time LiveScore keeps it in the *FT90 fields.
      const h90 = r.homeFT90 ?? r.homeGoals ?? 0, a90 = r.awayFT90 ?? r.awayGoals ?? 0;
      const ht = r.homeHT !== null && r.homeHT !== undefined && r.awayHT !== null && r.awayHT !== undefined;
      const firstDone = state === "post" || period === 2;
      matches.push({
        id: `ls-${r.id}`, slug: `ls:${r.league}`,
        home: { name: r.home, short: short(r.home), score: h90 }, away: { name: r.away, short: short(r.away), score: a90 },
        state, off, final: state === "post", period,
        name: r.status === "HT" ? "STATUS_HALFTIME" : "",
        detail: state === "pre" ? "" : r.status,
        // Before half time LiveScore has no HT score yet: the first half is the score so far.
        halves: ht && firstDone ? [[r.homeHT, r.awayHT], [h90 - r.homeHT, a90 - r.awayHT]]
          : state === "in" ? [[h90, a90], [0, 0]] : null,
      });
    }
    return matches;
  }

  // Bets logged on the goals page ("My bets", kept in this browser):
  // { id, date: "YYYY-MM-DD", mk: "o15"|"gibh", title, bookie, stake, ret,
  //   legs: [{ key, fx: "Home v Away", lg: league name, role }] }
  // relay: true once the Cloudflare relay is set up, so the four leagues ESPN
  // doesn't cover are followed live too.
  function goalsPageBets(stored, relay = false) {
    return (Array.isArray(stored) ? stored : []).filter(b => b && Array.isArray(b.legs)).map(b => {
      const date = String(b.date || "").replace(/-/g, "");
      return {
        id: `goals-${b.id}`, book: b.bookie || "", kind: `${b.legs.length}-fold ${b.mk === "gibh" ? "Goal in both halves" : "Over 1.5 goals"}`,
        odds: "", stake: b.stake, returns: b.ret, dates: date ? [date] : [], source: "goals page",
        legs: b.legs.map(l => {
          const [home, away] = String(l.fx || "").split(" v ");
          const league = GOALS_LEAGUES[l.lg] || (relay ? RELAY_LEAGUES[l.lg] : undefined);
          if (!league) return { type: "other", label: `${l.fx} (${l.lg})`, note: "no live feed for this league" };
          const leg = { sport: "soccer", league, date, home, away };
          return b.mk === "gibh" ? { ...leg, type: "gibh" } : { ...leg, type: "goals", side: "over", line: 1.5 };
        }),
      };
    });
  }

  // How a bet's legs are laid out: what's still to be decided at the top (in
  // play and short of the line, then in play and there, then not started),
  // then lost legs, then won, then void. Slip order within each group.
  const LEG_GROUP = { lost: "lost", won: "won", void: "void" };
  const OPEN_RANK = { losing: 0, winning: 1, unknown: 2, pending: 3 };
  function groupLegs(legs) {
    const groups = { open: [], lost: [], won: [], void: [] };
    for (const l of legs) groups[LEG_GROUP[l.status] || "open"].push(l);
    groups.open.sort((a, b) => (OPEN_RANK[a.status] ?? 2) - (OPEN_RANK[b.status] ?? 2));
    return groups;
  }

  const api = { STATS, nameKey, parseScoreboard, parseBoxscore, findPlayer, statValue, touchdowns,
    evaluateLeg, evaluateBet, progressText,
    GOALS_LEAGUES, RELAY_LEAGUES, SEARCH_LEAGUES, parseRelay, clubScore, parseSoccerBoard, findMatch, soccerHalves, soccerLegNeedsSummary,
    evaluateSoccerLeg, soccerProgress, goalsPageBets, groupLegs };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.TrackerCore = api;
})(typeof window !== "undefined" ? window : globalThis);
