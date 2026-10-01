import pytest

from analyst_sweep import (
    match_picks_to_candidate,
    normalize_market,
    parse_picks_json,
    summarize_sources,
)


def _pick(outlet="Action Network", analyst="Jane Doe", player="Drake Maye",
          market="player_pass_yds", side="over", line=214.5):
    return {"outlet": outlet, "analyst": analyst, "player": player, "market": market, "side": side, "line": line}


# --- parse_picks_json ------------------------------------------------------

def test_parse_picks_json_plain_array():
    picks = parse_picks_json('[{"outlet": "ESPN", "player": "Drake Maye"}]')
    assert len(picks) == 1
    assert picks[0]["player"] == "Drake Maye"


def test_parse_picks_json_strips_markdown_fence():
    text = '```json\n[{"outlet": "ESPN"}]\n```'
    picks = parse_picks_json(text)
    assert picks == [{"outlet": "ESPN"}]


def test_parse_picks_json_empty_array():
    assert parse_picks_json("[]") == []


def test_parse_picks_json_non_json_returns_empty_not_raises():
    assert parse_picks_json("I couldn't find any picks for this game.") == []


def test_parse_picks_json_non_list_json_returns_empty():
    assert parse_picks_json('{"not": "a list"}') == []


# --- match_picks_to_candidate -----------------------------------------------

def test_match_picks_to_candidate_exact_match():
    picks = [_pick(player="Drake Maye", market="player_pass_yds", line=214.5)]
    matched = match_picks_to_candidate(picks, "Drake Maye", "player_pass_yds", 214.5)
    assert len(matched) == 1


def test_match_picks_to_candidate_fuzzy_name_match():
    # Same real near-match example match_players.py itself is built around
    picks = [_pick(player="Kenneth Walker III", market="player_pass_yds", line=214.5)]
    matched = match_picks_to_candidate(picks, "Kenneth Walker", "player_pass_yds", 214.5)
    assert len(matched) == 1


def test_match_picks_to_candidate_rejects_abbreviated_initial():
    # "D. Maye" is deliberately NOT treated as a safe match for "Drake
    # Maye" -- an initial-only first name is too weak a signal (it could
    # be a different player entirely) to risk a false match on.
    picks = [_pick(player="D. Maye", market="player_pass_yds", line=214.5)]
    matched = match_picks_to_candidate(picks, "Drake Maye", "player_pass_yds", 214.5)
    assert matched == []


def test_match_picks_to_candidate_within_line_tolerance():
    picks = [_pick(line=213.0)]  # 1.5 off the candidate's 214.5, within default 2.0 tolerance
    matched = match_picks_to_candidate(picks, "Drake Maye", "player_pass_yds", 214.5)
    assert len(matched) == 1


def test_match_picks_to_candidate_rejects_line_outside_tolerance():
    picks = [_pick(line=205.0)]
    matched = match_picks_to_candidate(picks, "Drake Maye", "player_pass_yds", 214.5)
    assert matched == []


def test_match_picks_to_candidate_rejects_wrong_market():
    picks = [_pick(market="player_reception_yds")]
    matched = match_picks_to_candidate(picks, "Drake Maye", "player_pass_yds", 214.5)
    assert matched == []


def test_match_picks_to_candidate_rejects_wrong_player():
    picks = [_pick(player="Someone Else")]
    matched = match_picks_to_candidate(picks, "Drake Maye", "player_pass_yds", 214.5)
    assert matched == []


def test_match_picks_to_candidate_handles_missing_line():
    picks = [{"player": "Drake Maye", "market": "player_pass_yds", "side": "over", "line": None}]
    matched = match_picks_to_candidate(picks, "Drake Maye", "player_pass_yds", 214.5)
    assert matched == []


# --- summarize_sources -------------------------------------------------

def test_summarize_sources_counts_independent_analysts():
    picks = [_pick(analyst="A"), _pick(analyst="B"), _pick(analyst="C")]
    consensus = summarize_sources(picks)
    assert consensus.n_over_sources == 3
    assert consensus.contested is False


def test_summarize_sources_dedups_syndicated_analyst():
    # Same analyst, same pick, republished on a second outlet -- counts once
    picks = [
        _pick(outlet="Action Network", analyst="Jane Doe"),
        _pick(outlet="Yahoo", analyst="Jane Doe"),
        _pick(outlet="Covers", analyst="Bob Smith"),
    ]
    consensus = summarize_sources(picks)
    assert consensus.n_over_sources == 2


def test_summarize_sources_flags_contested_when_analyst_backs_under():
    picks = [_pick(analyst="A", side="over"), _pick(analyst="B", side="over"), _pick(analyst="C", side="under")]
    consensus = summarize_sources(picks)
    assert consensus.contested is True
    assert len(consensus.under_sources) == 1


def test_summarize_sources_flags_crowding_at_threshold():
    picks = [
        _pick(outlet="Action Network", analyst="A"),
        _pick(outlet="Covers", analyst="B"),
        _pick(outlet="SI", analyst="C"),
        _pick(outlet="ESPN", analyst="D"),
    ]
    consensus = summarize_sources(picks, crowding_flag_outlets=4)
    assert consensus.crowded is True


def test_summarize_sources_not_crowded_below_threshold():
    picks = [_pick(outlet="Action Network", analyst="A"), _pick(outlet="Covers", analyst="B")]
    consensus = summarize_sources(picks, crowding_flag_outlets=4)
    assert consensus.crowded is False


def test_summarize_sources_unnamed_analysts_at_one_outlet_count_once():
    # The real smoke test returned several unnamed "Action Network" picks
    # that were one syndicated Yahoo article -- one source, not several.
    picks = [_pick(analyst=None), _pick(analyst=None)]
    assert summarize_sources(picks).n_over_sources == 1


def test_summarize_sources_unnamed_analysts_at_different_outlets_count_separately():
    picks = [_pick(analyst=None, outlet="Covers"), _pick(analyst=None, outlet="SI")]
    assert summarize_sources(picks).n_over_sources == 2


def test_summarize_sources_reads_sides_as_articles_write_them():
    picks = [_pick(analyst="A", side="Over"), _pick(analyst="B", side=" OVER "), _pick(analyst="C", side="Under")]
    consensus = summarize_sources(picks)
    assert consensus.n_over_sources == 2
    assert consensus.contested is True


@pytest.mark.parametrize("text, key", [
    ("Receiving Yards", "player_reception_yds"), ("Rec Yds", "player_reception_yds"),
    ("Receptions", "player_receptions"), ("Passing Yards", "player_pass_yds"),
    ("Passing Touchdowns", "player_pass_tds"), ("Pass Completions", "player_pass_completions"),
    ("Interceptions Thrown", "player_pass_interceptions"), ("Rushing Yards", "player_rush_yds"),
    ("Rushing Attempts", "player_rush_attempts"), ("Carries", "player_rush_attempts"),
    ("Tackles + Assists", "player_tackles_assists"), ("Sacks", "player_sacks"),
    ("player_pass_yds", "player_pass_yds"),
    ("Rush + Rec Yards", None), ("Rushing and Receiving Yards", None), ("Anytime Touchdown Scorer", None),
    ("Longest Reception", None), ("Longest Rush", None), ("Pass Attempts", None), (None, None), ("", None),
])
def test_normalize_market(text, key):
    assert normalize_market(text) == key


def test_match_picks_to_candidate_reads_markets_as_articles_write_them():
    picks = [_pick(market="Passing Yards", side="Over")]
    assert match_picks_to_candidate(picks, "Drake Maye", "player_pass_yds", 214.5) == picks


def test_match_picks_to_candidate_ignores_non_numeric_lines():
    assert match_picks_to_candidate([_pick(line="o214.5")], "Drake Maye", "player_pass_yds", 214.5) == []


# --- the API call path, with a fake client ------------------------------------

from types import SimpleNamespace

import analyst_sweep


def _response(stop_reason, text="", searches=2, in_tok=1000, out_tok=500):
    usage = SimpleNamespace(
        input_tokens=in_tok, output_tokens=out_tok, cache_read_input_tokens=0, cache_creation_input_tokens=None,
        server_tool_use=SimpleNamespace(web_search_requests=searches),
    )
    content = [SimpleNamespace(type="server_tool_use")] + ([SimpleNamespace(type="text", text=text)] if text else [])
    return SimpleNamespace(stop_reason=stop_reason, usage=usage, content=content)


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _install(monkeypatch, responses):
    client = _FakeClient(responses)
    monkeypatch.setattr(analyst_sweep.anthropic, "Anthropic", lambda api_key=None: client)
    return client


def test_a_paused_turn_is_resumed_and_usage_adds_up(monkeypatch):
    pick_json = '[{"outlet": "Covers", "player": "Drake Maye", "market": "Passing Yards", "side": "Over", "line": 214.5}]'
    client = _install(monkeypatch, [_response("pause_turn"), _response("end_turn", text=pick_json)])
    picks, usage = analyst_sweep.fetch_analyst_picks_with_usage("Patriots at Jets", 4)
    assert picks[0]["outlet"] == "Covers"
    assert usage == {"input_tokens": 2000, "output_tokens": 1000, "web_searches": 4}
    resumed = client.calls[1]["messages"]
    assert [m["role"] for m in resumed] == ["user", "assistant"]  # no extra "continue" message


def test_api_failure_returns_no_picks_rather_than_crashing(monkeypatch):
    class Boom:
        messages = None

        def __init__(self):
            self.messages = self

        def create(self, **kwargs):
            raise analyst_sweep.anthropic.APIConnectionError(request=None)

    monkeypatch.setattr(analyst_sweep.anthropic, "Anthropic", lambda api_key=None: Boom())
    assert analyst_sweep.fetch_analyst_picks("Patriots at Jets", 4) == []


def test_sweep_games_totals_usage_and_cost(monkeypatch):
    _install(monkeypatch, [_response("end_turn", text="[]", searches=5, in_tok=100_000, out_tok=10_000)] * 2)
    results, totals = analyst_sweep.sweep_games(["A at B", "C at D"], 4, max_workers=1)
    assert set(results) == {"A at B", "C at D"}
    assert totals["web_searches"] == 10
    # 200k in x $2/M + 20k out x $10/M + 10 searches x $0.01
    assert totals["estimated_cost_usd"] == pytest.approx(0.4 + 0.2 + 0.1)


# The exact shape of the reply that lost every pick on the first live run
# (PIT @ CLE, Week 4): narration, then a fenced JSON block.
LIVE_WEEK4_REPLY = '''Good, there's real content. Let me fetch details from the most relevant and reputable sources.```json
[
  {
    "outlet": "Sports Illustrated (SI)",
    "analyst": null,
    "player": "Jaylen Warren",
    "market": "Rush + Receiving Yards",
    "side": "over",
    "line": 94.5,
    "price": -111,
    "book": "DraftKings",
    "publish_date": "2026-10-01",
    "url": "https://www.si.com/betting/steelers-vs-browns-best-nfl-prop-bets-for-thursday-night-football-in-week-4-bet-on-jaylen-warren",
    "track_record": null
  },
  {
    "outlet": "CBS Sports",
    "analyst": null,
    "player": "Jaylen Warren",
    "market": "Rushing Yards",
    "side": "over",
    "line": 70.5,
    "price": -120,
    "book": "BetMGM",
    "publish_date": "2026-10-01",
    "url": "https://www.cbssports.com/betting/news/steelers-vs-browns-odds-picks-prediction-best",
    "track_record": null
  }
]
```'''


def test_parse_picks_json_survives_narration_before_the_json():
    picks = parse_picks_json(LIVE_WEEK4_REPLY)
    assert [p["outlet"] for p in picks] == ["Sports Illustrated (SI)", "CBS Sports"]
    matched = match_picks_to_candidate(picks, "Jaylen Warren", "player_rush_yds", 70.5)
    assert [p["outlet"] for p in matched] == ["CBS Sports"]  # the combo market is correctly not a rushing-yards pick


def test_parse_picks_json_finds_a_bare_array_after_prose():
    assert parse_picks_json('Here is what I found:\n[{"outlet": "Covers"}]\nThat is all.') == [{"outlet": "Covers"}]


def test_parse_picks_json_prefers_the_last_fenced_block():
    text = 'Draft:```json\n[{"outlet": "old"}]\n```Final:```json\n[{"outlet": "new"}]\n```'
    assert parse_picks_json(text) == [{"outlet": "new"}]


def test_parse_picks_json_still_rejects_text_with_no_json():
    assert parse_picks_json("I couldn't find any picks for this game.") == []
