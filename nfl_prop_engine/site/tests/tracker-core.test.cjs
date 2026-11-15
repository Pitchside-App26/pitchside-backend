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
