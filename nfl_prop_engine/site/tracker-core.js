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

  function evaluateBet(bet, games, boxscores) {
    const legs = bet.legs.map(leg => ({ leg, ...evaluateLeg(leg, games, boxscores) }));
    const counts = s => legs.filter(l => l.status === s).length;
    let status;
    if (counts("lost")) status = "lost";
    else if (legs.every(l => l.status === "won" || l.status === "void")) status = "won";
    else if (legs.some(l => l.game && l.game.state === "in")) status = "live";
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

  const api = { STATS, nameKey, parseScoreboard, parseBoxscore, findPlayer, statValue, touchdowns,
    evaluateLeg, evaluateBet, progressText };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.TrackerCore = api;
})(typeof window !== "undefined" ? window : globalThis);
