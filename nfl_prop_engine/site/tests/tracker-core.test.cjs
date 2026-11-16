// node --test nfl_prop_engine/site/tests/
// (.cjs and loaded by hand: the repo's package.json says "type": "module",
// while tracker-core.js is a plain browser script.)
// Fixtures follow the shape of ESPN's real scoreboard and summary JSON
// (checked against the live feed on 15 Nov 2026).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const T = (() => {
  const mod = { exports: {} };
  new Function("module", fs.readFileSync(path.join(__dirname, "../tracker-core.js"), "utf8"))(mod);
  return mod.exports;
})();

function event(id, away, home, as, hs, state, detail = "") {
  return { id, status: { period: 2, displayClock: "8:36", type: { state, completed: state === "post", shortDetail: detail } },
    competitions: [{ competitors: [
      { homeAway: "home", score: String(hs), team: { abbreviation: home } },
      { homeAway: "away", score: String(as), team: { abbreviation: away } }] }] };
}
const SB = { events: [
  event("1", "KC", "ATL", 35, 13, "post", "Final"),
  event("2", "MIN", "GB", 30, 10, "post", "Final"),
  event("3", "SF", "DAL", 7, 3, "in", "2:42 - 1st"),
  event("4", "PIT", "CIN", 0, 0, "pre", "8:20 PM"),
  event("5", "HOU", "CLE", 20, 21, "post", "Final"),
] };

function cat(name, keys, rows) {
  return { name, keys, athletes: rows.map(([n, stats]) => ({ athlete: { displayName: n }, stats })) };
}
const SUMMARY = { boxscore: { players: [
  { team: { abbreviation: "SF" }, statistics: [
    cat("passing", ["completions/passingAttempts", "passingYards", "yardsPerPassAttempt", "passingTouchdowns", "interceptions"],
        [["Brock Purdy", ["4/4", "59", "14.8", "1", "0"]]]),
    cat("rushing", ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns", "longRushing"],
        [["Christian McCaffrey", ["6", "31", "5.2", "1", "12"]], ["Kaelon Black", ["2", "9", "4.5", "0", "6"]]]),
    cat("receiving", ["receptions", "receivingYards", "yardsPerReception", "receivingTouchdowns", "longReception", "receivingTargets"],
        [["George Kittle", ["3", "41", "13.7", "0", "22", "4"]]]),
  ] },
  { team: { abbreviation: "DAL" }, statistics: [
    cat("rushing", ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns", "longRushing"],
        [["Javonte Williams", ["7", "27", "3.9", "0", "8"]]]),
    cat("defensive", ["totalTackles", "soloTackles", "sacks"], [["DaRon Bland", ["2", "2", "0"]]]),
  ] },
] } };

const games = T.parseScoreboard(SB);
const boxes = { "3": T.parseBoxscore(SUMMARY) };
const leg = l => T.evaluateLeg(l, games, boxes);

test("scoreboard keys games by away@home with live state", () => {
  assert.equal(games["SF@DAL"].state, "in");
  assert.equal(games["KC@ATL"].final, true);
  assert.deepEqual([games["SF@DAL"].away.score, games["SF@DAL"].home.score], [7, 3]);
});

test("moneyline settles on the final score and shows live leads", () => {
  assert.equal(leg({ type: "moneyline", game: "KC@ATL", team: "KC" }).status, "won");
  assert.equal(leg({ type: "moneyline", game: "SF@DAL", team: "DAL" }).status, "losing");
});

test("game totals: overs lock in once passed, unders once the game ends", () => {
  assert.equal(leg({ type: "total", game: "MIN@GB", side: "over", line: 42 }).status, "lost");   // 40
  assert.equal(leg({ type: "total", game: "HOU@CLE", side: "over", line: 41 }).value, 41);
  assert.equal(leg({ type: "total", game: "HOU@CLE", side: "over", line: 41 }).status, "void"); // exactly 41: push
  assert.equal(leg({ type: "total", game: "SF@DAL", side: "over", line: 9.5 }).status, "won");  // 10 already
  assert.equal(leg({ type: "total", game: "SF@DAL", side: "under", line: 37.5 }).status, "winning");
  assert.equal(leg({ type: "total", game: "PIT@CIN", side: "over", line: 40 }).status, "pending");
});

test("player stats read the box score, initials included", () => {
  const purdy = leg({ type: "player", game: "SF@DAL", player: "Brock Purdy", stat: "passingYards", side: "over", line: 260.5 });
  assert.deepEqual([purdy.value, purdy.status], [59, "losing"]);
  assert.equal(T.progressText({ type: "player", side: "over", line: 260.5 }, purdy), "needs 202 more");
  assert.equal(leg({ type: "player", game: "SF@DAL", player: "J. Williams", stat: "rushingYards", side: "over", line: 61.5 }).value, 27);
  assert.equal(leg({ type: "player", game: "SF@DAL", player: "Brock Purdy", stat: "completions", side: "over", line: 3.5 }).status, "won");
  assert.equal(leg({ type: "player", game: "SF@DAL", player: "DaRon Bland", stat: "tackles", side: "under", line: 4.5 }).status, "winning");
});

test("a player with no stats yet is on 0, not missing", () => {
  const r = leg({ type: "player", game: "SF@DAL", player: "Ryan Flournoy", stat: "receivingYards", side: "over", line: 36.5 });
  assert.deepEqual([r.value, r.status, r.note], [0, "losing", "no stats yet"]);
});

test("anytime TD counts rushing and receiving touchdowns", () => {
  assert.equal(leg({ type: "anytime_td", game: "SF@DAL", player: "C. McCaffrey" }).status, "won");
  assert.equal(leg({ type: "anytime_td", game: "SF@DAL", player: "George Kittle" }).status, "losing");
});

test("a bet is lost on its first lost leg and won when every leg lands", () => {
  const acca = { legs: [{ type: "moneyline", game: "KC@ATL", team: "KC" }, { type: "total", game: "MIN@GB", side: "over", line: 42 }] };
  assert.equal(T.evaluateBet(acca, games, boxes).status, "lost");
  const live = { legs: [{ type: "moneyline", game: "KC@ATL", team: "KC" }, { type: "anytime_td", game: "SF@DAL", player: "Kittle" }] };
  const r = T.evaluateBet(live, games, boxes);
  assert.deepEqual([r.status, r.won, r.total], ["live", 1, 2]);
});

test("legs the tracker can't follow are shown, and a bet waits on them", () => {
  const other = { type: "other", label: "Purdy first TD scorer", note: "can't be followed live" };
  assert.deepEqual([leg(other).status, leg(other).note], ["unknown", "can't be followed live"]);
  const bet = { legs: [{ type: "moneyline", game: "KC@ATL", team: "KC" }, other] };
  assert.equal(T.evaluateBet(bet, games, boxes).status, "check");
  const lost = { legs: [{ type: "total", game: "MIN@GB", side: "over", line: 42 }, other] };
  assert.equal(T.evaluateBet(lost, games, boxes).status, "lost");
});

// ── Football ──  (shapes from ESPN's soccer feed, checked 16 Nov 2026)
function match(id, home, away, hs, as, state, name, period = 2, clock = "67'") {
  return { id, status: { period, displayClock: clock, type: { state, name, shortDetail: state === "post" ? "FT" : clock } },
    competitions: [{ competitors: [
      { homeAway: "home", score: String(hs), team: { displayName: home, abbreviation: home.slice(0, 3).toUpperCase() } },
      { homeAway: "away", score: String(as), team: { displayName: away, abbreviation: away.slice(0, 3).toUpperCase() } }] }] };
}
const L1 = T.parseSoccerBoard({ events: [
  match("a", "AFC Wimbledon", "Blackpool", 1, 0, "post", "STATUS_FULL_TIME"),
  match("b", "Manchester United", "Wolverhampton Wanderers", 1, 1, "in", "STATUS_SECOND_HALF"),
  match("c", "Stockport County", "Bolton Wanderers", 0, 0, "in", "STATUS_HALFTIME", 1, "45'"),
  match("d", "Exeter City", "Reading", 0, 0, "pre", "STATUS_SCHEDULED"),
  match("e", "Barnsley", "Wigan Athletic", 0, 0, "post", "STATUS_POSTPONED"),
] }, "eng.3");
const soccer = (leg, halves) => T.evaluateSoccerLeg(leg, T.findMatch(L1, leg.home, leg.away), halves);

test("matches are found despite different club names, never the wrong way round", () => {
  assert.equal(T.findMatch(L1, "Wimbledon", "Blackpool").id, "a");
  assert.equal(T.findMatch(L1, "Man Utd", "Wolves").id, "b");
  assert.equal(T.findMatch(L1, "Blackpool", "AFC Wimbledon"), null);
  assert.equal(T.findMatch(L1, "Arsenal", "Chelsea"), null);
});

test("match goals, BTTS and result settle on the score", () => {
  assert.equal(soccer({ type: "goals", home: "Wimbledon", away: "Blackpool", side: "over", line: 1.5 }).status, "lost");
  assert.equal(soccer({ type: "goals", home: "Man Utd", away: "Wolves", side: "over", line: 1.5 }).status, "won");
  const live = soccer({ type: "goals", home: "Stockport", away: "Bolton", side: "over", line: 1.5 });
  assert.deepEqual([live.status, T.soccerProgress({ type: "goals", side: "over", line: 1.5 }, live)], ["losing", "needs 2 more goals"]);
  assert.equal(soccer({ type: "btts", home: "Man Utd", away: "Wolves", side: "yes" }).status, "won");
  assert.equal(soccer({ type: "result", home: "AFC Wimbledon", away: "Blackpool", pick: "home" }).status, "won");
  assert.equal(soccer({ type: "goals", home: "Exeter", away: "Reading", side: "over", line: 1.5 }).status, "pending");
  assert.equal(soccer({ type: "goals", home: "Barnsley", away: "Wigan", side: "over", line: 1.5 }).status, "void");
});

test("goal in both halves needs the half scores", () => {
  const leg = { type: "gibh", home: "Man Utd", away: "Wolves" };
  assert.equal(soccer(leg, null).status, "unknown");
  assert.equal(soccer(leg, [[1, 0], [0, 1]]).status, "won");
  assert.equal(soccer(leg, [[1, 0], [0, 0]]).status, "winning");  // 2nd half still going
  assert.equal(soccer({ ...leg, home: "Stockport", away: "Bolton" }, [[0, 0], [0, 0]]).status, "lost");  // 0-0 at HT
  assert.equal(soccer({ ...leg, home: "Wimbledon", away: "Blackpool" }, [[1, 0], [0, 0]]).status, "lost");
});

test("half scores come from the summary's line scores", () => {
  const summary = { header: { competitions: [{ competitors: [
    { homeAway: "home", linescores: [{ displayValue: "1" }, { displayValue: "0" }] },
    { homeAway: "away", linescores: [{ displayValue: "0" }, { displayValue: "0" }] }] }] } };
  assert.deepEqual(T.soccerHalves(summary), [[1, 0], [0, 0]]);
});

test("goals-page bets become tracker bets, with unfed leagues marked", () => {
  const [bet] = T.goalsPageBets([{ id: "x1", date: "2026-11-14", mk: "o15", bookie: "SpreadEx", stake: 5, ret: 31.2,
    legs: [{ fx: "AFC Wimbledon v Blackpool", lg: "League One", role: "leg" },
           { fx: "Chorley v Darlington", lg: "National League North", role: "leg" }] }]);
  assert.deepEqual([bet.book, bet.kind, bet.dates], ["SpreadEx", "2-fold Over 1.5 goals", ["20261114"]]);
  assert.deepEqual(bet.legs[0], { sport: "soccer", league: "eng.3", date: "20261114", home: "AFC Wimbledon",
    away: "Blackpool", type: "goals", side: "over", line: 1.5 });
  assert.equal(bet.legs[1].type, "other");
  const r = T.evaluateBet(bet, {}, {}, leg => T.evaluateSoccerLeg(leg, T.findMatch(L1, leg.home, leg.away), null));
  assert.equal(r.status, "lost");
});

// ── Lower leagues through the Cloudflare relay ──
// LiveScore event shapes as seen on 14 Nov 2026 (Airdrieonians 2-0 Queen of the South, HT 1-0).
const LIVESCORE = { Stages: [
  { Cnm: "Scotland", Snm: "League 1", Events: [
    { Eid: "1793390", T1: [{ Nm: "Airdrieonians" }], T2: [{ Nm: "Queen of the South" }], Eps: "FT", Esd: 20261114150000,
      Tr1: "2", Tr2: "0", Trh1: "1", Trh2: "0" },
    { Eid: "2", T1: [{ Nm: "Montrose" }], T2: [{ Nm: "Alloa Athletic" }], Eps: "67'", Esd: 20261114150000,
      Tr1: "1", Tr2: "0", Trh1: "1", Trh2: "0" },
    { Eid: "3", T1: [{ Nm: "Kelty Hearts" }], T2: [{ Nm: "Cove Rangers" }], Eps: "23'", Esd: 20261114150000, Tr1: "0", Tr2: "0" }] },
  { Cnm: "England", Snm: "National League: North", Events: [
    { Eid: "4", T1: [{ Nm: "Chorley" }], T2: [{ Nm: "Darlington" }], Eps: "Postp.", Esd: 20261114150000 }] },
  { Cnm: "England", Snm: "Premier League", Events: [{ Eid: "5", T1: [{ Nm: "X" }], T2: [{ Nm: "Y" }], Eps: "FT" }] },
] };

test("the relay keeps only the four leagues, in the shape the tracker reads", async () => {
  const { pathToFileURL } = require("node:url");
  const worker = await import(pathToFileURL(path.join(__dirname, "../../../relay/lower-leagues-worker.js")).href);
  const picked = worker.pickMatches(LIVESCORE);
  assert.deepEqual(picked.map(m => m.league), ["sco3", "sco3", "sco3", "north"]);
  assert.deepEqual(picked[0], { league: "sco3", id: "1793390", home: "Airdrieonians", away: "Queen of the South",
    status: "FT", kickoff: "20261114150000", homeGoals: 2, awayGoals: 0, homeHT: 1, awayHT: 0, homeFT90: null, awayFT90: null });

  const matches = T.parseRelay({ matches: picked });
  const [ft, live2nd, live1st, postponed] = matches;
  assert.deepEqual([ft.state, ft.final, ft.halves], ["post", true, [[1, 0], [1, 0]]]);
  assert.deepEqual([live2nd.state, live2nd.period, live2nd.halves], ["in", 2, [[1, 0], [0, 0]]]);
  assert.deepEqual([live1st.period, live1st.halves], [1, [[0, 0], [0, 0]]]);
  assert.equal(postponed.off, true);

  const gibh = leg => T.evaluateSoccerLeg(leg, T.findMatch(matches, leg.home, leg.away), T.findMatch(matches, leg.home, leg.away).halves);
  assert.equal(gibh({ type: "gibh", home: "Airdrie", away: "Queen of Sth" }).status, "won");
  assert.equal(gibh({ type: "gibh", home: "Montrose", away: "Alloa" }).status, "winning");
  assert.equal(gibh({ type: "goals", home: "Kelty Hearts", away: "Cove Rangers", side: "over", line: 1.5 }).status, "losing");
  assert.equal(gibh({ type: "goals", home: "Chorley", away: "Darlington", side: "over", line: 1.5 }).status, "void");
});

test("goals-page legs in those leagues are followed once the relay is set up", () => {
  const stored = [{ id: "z", date: "2026-11-14", mk: "o15", bookie: "SpreadEx", stake: 5, ret: 20,
    legs: [{ fx: "Airdrieonians v Queen of the South", lg: "Scottish League One" }] }];
  assert.equal(T.goalsPageBets(stored, false)[0].legs[0].type, "other");
  assert.deepEqual(T.goalsPageBets(stored, true)[0].legs[0], { sport: "soccer", league: "ls:sco3", date: "20261114",
    home: "Airdrieonians", away: "Queen of the South", type: "goals", side: "over", line: 1.5 });
});

test("groupLegs: undecided legs first, then lost, won and void, slip order kept within each", () => {
  const legs = ["won", "pending", "winning", "lost", "losing", "void", "won", "pending"].map((status, i) => ({ status, i }));
  const g = T.groupLegs(legs);
  assert.deepEqual(g.open.map(l => l.i), [4, 2, 1, 7]);
  assert.deepEqual(g.lost.map(l => l.i), [3]);
  assert.deepEqual(g.won.map(l => l.i), [0, 6]);
  assert.deepEqual(g.void.map(l => l.i), [5]);
});
