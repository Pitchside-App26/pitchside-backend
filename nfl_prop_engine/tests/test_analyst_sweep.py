import pytest

from analyst_sweep import (
    match_picks_to_candidate,
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


def test_summarize_sources_unnamed_analysts_each_count_as_own_source():
    picks = [_pick(analyst=None), _pick(analyst=None)]
    consensus = summarize_sources(picks)
    assert consensus.n_over_sources == 2
