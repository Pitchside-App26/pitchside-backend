import sqlite3

import pytest

from bet_slips import (
    RESPONSE_SCHEMA,
    already_handled,
    classify_command,
    detect_media_type,
    extract_image_urls,
    latest_draft,
    normalize,
    odds_to_decimal,
    render_draft_comment,
    status_comment,
    strip_images,
)
from prop_bets_log import AlreadySettledError, replace_slips_for_issue, settle_week

BOT = {"login": "github-actions[bot]", "type": "Bot"}
DAN = {"login": "Pitchside-App26", "type": "User"}


def _leg(player="Drake Maye", market="player_pass_yds", side="over", line=214.5, odds="5/6", bb=None):
    return {
        "player": player, "team": None, "event": None, "market_text": "Passing Yards", "market": market,
        "side": side, "line": line, "odds": odds, "bet_builder_group": bb,
    }


def _parsed(legs, bet_type="accumulator", stake=5.0, total="11/2", returns=32.5, week=None, unclear=None):
    return {
        "is_bet_slip": True, "week": week, "unclear": unclear,
        "slips": [{"bet_type": bet_type, "stake_gbp": stake, "total_odds": total,
                   "potential_returns_gbp": returns, "legs": legs}],
    }


# --- odds conversion ---------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("5/6", 1.8333), ("evens", 2.0), ("11/2", 6.5), ("1.83", 1.83), ("+150", 2.5), ("-110", 1.9091),
])
def test_odds_to_decimal_handles_every_displayed_format(raw, expected):
    assert odds_to_decimal(raw) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize("raw", [None, "", "abc", "0.5", "5/0"])
def test_odds_to_decimal_returns_none_rather_than_guessing(raw):
    assert odds_to_decimal(raw) is None


# --- normalize ---------------------------------------------------------------

def test_normalize_consistent_slip_has_no_warnings():
    # 5/6 x 11/10 x 2/1 = 1.8333 x 2.1 x 3.0 = 11.55 ~ 21/2 (11.5)
    legs = [_leg(odds="5/6"), _leg("Garrett Wilson", "player_reception_yds", odds="11/10"), _leg("Tony Pollard", "player_rush_yds", odds="2/1")]
    draft = normalize(_parsed(legs, total="21/2", stake=5.0, returns=57.5), week=4, roster_names=None)
    assert draft["warnings"] == []
    assert draft["week"] == 4
    assert draft["slips"][0]["total_odds_decimal"] == pytest.approx(11.5)
    assert draft["slips"][0]["legs"][0]["book_price"] == pytest.approx(1.8333, abs=1e-4)


def test_normalize_flags_leg_odds_that_dont_multiply_to_the_total():
    legs = [_leg(odds="5/6"), _leg("Garrett Wilson", odds="5/6")]
    draft = normalize(_parsed(legs, total="11/2", returns=32.5), week=4, roster_names=None)
    assert any("multiply to" in w for w in draft["warnings"])


def test_normalize_skips_multiply_check_for_bet_builder_legs():
    legs = [_leg(odds=None, bb="BB1"), _leg("Garrett Wilson", odds=None, bb="BB1")]
    draft = normalize(_parsed(legs, total="11/2", returns=32.5), week=4, roster_names=None)
    assert not any("multiply to" in w for w in draft["warnings"])


def test_normalize_flags_returns_that_dont_match_stake_times_odds():
    draft = normalize(_parsed([_leg(odds="11/2")], bet_type="single", total="11/2", returns=40.0), week=4, roster_names=None)
    assert any("should return" in w for w in draft["warnings"])


def test_normalize_matches_names_to_the_roster():
    draft = normalize(_parsed([_leg("Kenneth Walker")], bet_type="single", total="5/6", returns=None),
                      week=4, roster_names=["Kenneth Walker III", "Drake Maye"], overrides={})
    leg = draft["slips"][0]["legs"][0]
    assert leg["player"] == "Kenneth Walker III"
    assert leg["player_raw"] == "Kenneth Walker"


def test_normalize_keeps_and_flags_an_unmatched_name():
    draft = normalize(_parsed([_leg("Nobody Real")], bet_type="single", total="5/6", returns=None),
                      week=4, roster_names=["Drake Maye"], overrides={})
    assert draft["slips"][0]["legs"][0]["player"] == "Nobody Real"
    assert any("couldn't match" in w for w in draft["warnings"])


def test_normalize_week_from_correction_overrides_the_hint():
    assert normalize(_parsed([_leg()], week=5), week=4, roster_names=None)["week"] == 5


def test_normalize_warns_when_week_unknown():
    draft = normalize(_parsed([_leg()]), week=None, roster_names=None)
    assert any("week" in w.lower() for w in draft["warnings"])


def test_normalize_flags_over_under_leg_without_a_line():
    draft = normalize(_parsed([_leg(line=None)], bet_type="single", total="5/6", returns=None), week=4, roster_names=None)
    assert any("no line" in w for w in draft["warnings"])


def test_normalize_flags_screenshot_with_no_bet():
    draft = normalize({"is_bet_slip": False, "week": None, "unclear": None, "slips": []}, week=4, roster_names=None)
    assert draft["slips"] == []
    assert any("No placed bet" in w for w in draft["warnings"])


# --- draft comment round trip and trust --------------------------------------

def test_draft_round_trips_through_the_comment():
    draft = normalize(_parsed([_leg()], bet_type="single", total="5/6", returns=None), week=4, roster_names=None)
    body = render_draft_comment(draft)
    assert "Drake Maye" in body and "Pass Yds over 214.5" in body and "5/6 (1.83)" in body
    assert latest_draft([{"user": BOT, "body": body}]) == draft


def test_latest_draft_ignores_drafts_posted_by_anyone_else():
    draft = normalize(_parsed([_leg()]), week=4, roster_names=None)
    forged = render_draft_comment(draft)
    assert latest_draft([{"user": DAN, "body": forged}]) is None
    assert latest_draft([{"user": {"login": "github-actions[bot]", "type": "User"}, "body": forged}]) is None


def test_latest_draft_returns_the_newest_bot_draft():
    old = normalize(_parsed([_leg(line=200.5)]), week=4, roster_names=None)
    new = normalize(_parsed([_leg(line=214.5)]), week=4, roster_names=None)
    comments = [{"user": BOT, "body": render_draft_comment(old)}, {"user": DAN, "body": "line is 214.5"},
                {"user": BOT, "body": render_draft_comment(new)}]
    assert latest_draft(comments)["slips"][0]["legs"][0]["book_line"] == 214.5


def test_render_escapes_table_breaking_characters():
    leg = _leg(market="other")
    leg["market_text"] = "Win | Draw"
    body = render_draft_comment(normalize(_parsed([leg], bet_type="single", total="5/6", returns=None), 4, None))
    assert "Win / Draw" in body


def test_already_handled_only_counts_bot_replies():
    assert already_handled([{"user": BOT, "body": status_comment("Couldn't find a screenshot")}])
    assert not already_handled([{"user": DAN, "body": status_comment("fake")}])
    assert not already_handled([])


# --- commands ----------------------------------------------------------------

@pytest.mark.parametrize("body, command", [
    ("confirm", "confirm"), ("Confirm.", "confirm"), ("confirmed!", "confirm"), ("Yes", "confirm"),
    ("\N{THUMBS UP SIGN}", "confirm"), ("cancel", "cancel"), ("Retry", "retry"),
    ("leg 2 line is 64.5", "correction"), ("yes but leg 2 is wrong", "correction"), ("week is 5", "correction"),
])
def test_classify_command(body, command):
    assert classify_command(body) == command


# --- images ------------------------------------------------------------------

def test_extract_image_urls_keeps_only_github_uploads():
    body_html = (
        '<p><img src="https://private-user-images.githubusercontent.com/1/abc.png?jwt=x&amp;y=1" alt="slip"></p>'
        '<img src="https://github.com/user-attachments/assets/1234-abcd">'
        '<img src="https://camo.githubusercontent.com/external">'
        '<img src="https://evil.example.com/x.png">'
        '<img src="http://private-user-images.githubusercontent.com/insecure.png">'
        '<img src="https://github.com/someone/repo/raw/main/x.png">'
        '<img src="https://github.com/user-attachments/assets/1234-abcd">'
    )
    assert extract_image_urls(body_html) == [
        "https://private-user-images.githubusercontent.com/1/abc.png?jwt=x&y=1",
        "https://github.com/user-attachments/assets/1234-abcd",
    ]


def test_extract_image_urls_handles_missing_body():
    assert extract_image_urls(None) == []


@pytest.mark.parametrize("data, media_type", [
    (b"\x89PNG\r\n\x1a\n rest", "image/png"),
    (b"\xff\xd8\xff\xe0 rest", "image/jpeg"),
    (b"GIF89a rest", "image/gif"),
    (b"RIFF\x00\x00\x00\x00WEBP rest", "image/webp"),
    (b"\x00\x00\x00\x18ftypheic rest", "heic"),
    (b"%PDF-1.7", None),
])
def test_detect_media_type(data, media_type):
    assert detect_media_type(data) == media_type


def test_strip_images_leaves_the_notes():
    body = "![slip](https://github.com/user-attachments/assets/1)\n<img src=\"x\" width=300>\nStake was £10"
    assert strip_images(body) == "Stake was £10"


# --- structured output schema --------------------------------------------------

def _objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for value in schema.values():
            yield from _objects(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _objects(value)


def test_response_schema_meets_structured_output_rules():
    for obj in _objects(RESPONSE_SCHEMA):
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])


# --- logging a confirmed draft -----------------------------------------------

def _draft(line=214.5, stake=5.0):
    legs = [_leg(line=line, odds="5/6"), _leg("Garrett Wilson", "player_reception_yds", line=65.5, odds="5/6")]
    return normalize(_parsed(legs, stake=stake, total="9/4", returns=stake * 3.25), week=4, roster_names=None)


def _counts(db):
    conn = sqlite3.connect(db)
    counts = (conn.execute("SELECT COUNT(*) FROM bet_slips").fetchone()[0],
              conn.execute("SELECT COUNT(*) FROM prop_bets").fetchone()[0])
    conn.close()
    return counts


def test_confirming_twice_never_double_counts(tmp_path):
    db = str(tmp_path / "log.sqlite3")
    draft = _draft()
    assert replace_slips_for_issue(7, 4, draft["slips"], db_path=db) == (1, 2)
    assert replace_slips_for_issue(7, 4, draft["slips"], db_path=db) == (1, 2)
    assert _counts(db) == (1, 2)


def test_a_corrected_confirm_replaces_the_logged_version(tmp_path):
    db = str(tmp_path / "log.sqlite3")
    replace_slips_for_issue(7, 4, _draft(line=200.5, stake=5.0)["slips"], db_path=db)
    replace_slips_for_issue(7, 4, _draft(line=214.5, stake=10.0)["slips"], db_path=db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT stake_gbp, total_odds_decimal FROM bet_slips").fetchall() == [(10.0, 3.25)]
    assert conn.execute("SELECT book_line FROM prop_bets WHERE player='Drake Maye'").fetchall() == [(214.5,)]
    conn.close()


def test_other_issues_are_untouched_by_a_replace(tmp_path):
    db = str(tmp_path / "log.sqlite3")
    replace_slips_for_issue(7, 4, _draft()["slips"], db_path=db)
    replace_slips_for_issue(8, 4, _draft()["slips"], db_path=db)
    replace_slips_for_issue(8, 4, _draft()["slips"], db_path=db)
    assert _counts(db) == (2, 4)


def test_a_settled_bet_cannot_be_replaced(tmp_path):
    db = str(tmp_path / "log.sqlite3")
    replace_slips_for_issue(7, 4, _draft()["slips"], db_path=db)
    settle_week(4, {("Drake Maye", "player_pass_yds"): 250.0}, db_path=db)
    with pytest.raises(AlreadySettledError):
        replace_slips_for_issue(7, 4, _draft(line=200.5)["slips"], db_path=db)
    assert _counts(db) == (1, 2)


def test_settlement_skips_legs_it_cannot_grade(tmp_path):
    # Before this fix, an anytime-TD "yes" leg fell through to the under branch.
    db = str(tmp_path / "log.sqlite3")
    legs = [_leg("Johnny Mundt", "player_anytime_td", side="yes", line=None, odds="7/1"),
            _leg("Johnny Mundt", "player_receptions", side="over", line=None, odds="5/6")]
    replace_slips_for_issue(9, 4, normalize(_parsed(legs, bet_type="single", total=None, returns=None), 4, None)["slips"], db_path=db)
    count = settle_week(4, {("Johnny Mundt", "player_anytime_td"): 1.0, ("Johnny Mundt", "player_receptions"): 3.0}, db_path=db)
    assert count == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM prop_bets WHERE result IS NOT NULL").fetchone()[0] == 0
    conn.close()
