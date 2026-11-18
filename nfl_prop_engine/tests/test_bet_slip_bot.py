"""The bot's flow end to end, with GitHub and the Claude API stubbed out."""
import sqlite3

import pytest

import bet_slip_bot
import bet_slips
import prop_bets_log

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
BOT = {"login": "github-actions[bot]", "type": "Bot"}
DAN = {"login": "Pitchside-App26", "type": "User"}
STRANGER = {"login": "someone-else", "type": "User"}

PARSED = {
    "is_bet_slip": True, "week": None, "unclear": None,
    "slips": [{
        "bet_type": "single", "stake_gbp": 5.0, "total_odds": "5/6", "potential_returns_gbp": 9.17,
        "legs": [{"player": "Drake Maye", "team": None, "event": None, "market_text": "Passing Yards",
                  "market": "player_pass_yds", "side": "over", "line": 214.5, "odds": "5/6",
                  "bet_builder_group": None}],
    }],
}


class FakeGitHub:
    def __init__(self, body_html='<img src="https://github.com/user-attachments/assets/abc">'):
        self.issue = {"number": 5, "body": "", "body_html": body_html, "labels": [{"name": "bet-slip"}]}
        self.comments = []
        self.posted = []
        self.closed = None
        self.comment_by_id = {}

    def add_comment(self, user, body, comment_id=None, body_html=None):
        comment = {"id": comment_id or len(self.comments) + 1, "user": user, "body": body, "body_html": body_html}
        self.comments.append(comment)
        self.comment_by_id[comment["id"]] = comment
        return comment["id"]


@pytest.fixture
def gh(monkeypatch, tmp_path):
    fake = FakeGitHub()
    db = str(tmp_path / "log.sqlite3")
    monkeypatch.setenv("GITHUB_REPOSITORY_OWNER", "Pitchside-App26")
    monkeypatch.setattr(bet_slip_bot, "get_issue", lambda n: fake.issue)
    monkeypatch.setattr(bet_slip_bot, "list_comments", lambda n: list(fake.comments))
    monkeypatch.setattr(bet_slip_bot, "get_comment", lambda cid: fake.comment_by_id[cid])

    def post(n, body):
        fake.posted.append(body)
        fake.add_comment(BOT, body)

    monkeypatch.setattr(bet_slip_bot, "post_comment", post)
    monkeypatch.setattr(bet_slip_bot, "close_issue", lambda n, reason: setattr(fake, "closed", reason))
    monkeypatch.setattr(bet_slip_bot, "ensure_label", lambda n, labels: None)
    fake.downloaded = []

    def download(urls):
        fake.downloaded.append(list(urls))
        return [("image/png", PNG)] * len(urls), []

    monkeypatch.setattr(bet_slip_bot, "download_images", download)
    monkeypatch.setattr(bet_slip_bot, "current_week", lambda: 4)
    monkeypatch.setattr(bet_slip_bot, "roster_names", lambda: None)
    monkeypatch.setattr(bet_slip_bot, "RESULTS_DB_PATH", db)
    monkeypatch.setattr(bet_slip_bot, "replace_slips_for_issue",
                        lambda n, w, s: prop_bets_log.replace_slips_for_issue(n, w, s, db_path=db))
    monkeypatch.setattr(bet_slips, "parse_slip_images", lambda images, **kw: PARSED)
    import pandas as pd
    import tracker_bets
    games = pd.DataFrame([{"away_team": "NE", "home_team": "NYJ", "gameday": "2026-10-04"}])
    monkeypatch.setattr(bet_slip_bot, "tracker_context",
                        lambda week: (tracker_bets.Schedule(games), {"Drake Maye": "NE"}))
    fake.bets_path = str(tmp_path / "bets.json")
    monkeypatch.setattr(tracker_bets, "BETS_PATH", fake.bets_path)
    import price_log
    fake.prices_path = str(tmp_path / "placed_legs.csv")
    monkeypatch.setattr(price_log, "PATH", fake.prices_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "Pitchside-App26/pitchside-backend")
    fake.db = db
    return fake


def test_intake_posts_a_draft(gh):
    bet_slip_bot.cmd_intake(5)
    assert len(gh.posted) == 1
    assert bet_slips.latest_draft(gh.comments)["week"] == 4


def test_duplicate_intake_trigger_posts_nothing_more(gh):
    bet_slip_bot.cmd_intake(5)
    bet_slip_bot.cmd_intake(5)
    assert len(gh.posted) == 1


def test_intake_without_an_image_asks_for_one(gh):
    gh.issue["body_html"] = "<p>no picture</p>"
    bet_slip_bot.cmd_intake(5)
    assert "couldn't find a screenshot" in gh.posted[0]
    bet_slip_bot.cmd_intake(5)
    assert len(gh.posted) == 1


def test_confirm_logs_and_hands_the_reply_to_the_workflow(gh, tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    bet_slip_bot.cmd_intake(5)
    cid = gh.add_comment(DAN, "confirm", comment_id=100)
    reply = tmp_path / "reply.md"
    bet_slip_bot.cmd_comment(5, cid, str(reply))

    assert "logged=true" in out.read_text()
    assert "Logged 1 NFL bet (1 leg) to Week 4" in reply.read_text()
    conn = sqlite3.connect(gh.db)
    assert conn.execute("SELECT player, book_line, book_price FROM prop_bets").fetchall() == [
        ("Drake Maye", 214.5, pytest.approx(1.8333, abs=1e-4))
    ]
    conn.close()
    assert len(gh.posted) == 1  # the workflow posts the reply only after the commit is pushed
    assert "tracker=true" in out.read_text()
    assert "1 of 1 leg followed live: https://pitchside-app26.github.io/pitchside-backend/tracker.html" in reply.read_text()
    import json
    [bet] = json.load(open(gh.bets_path))["bets"]
    assert bet["legs"] == [{"type": "player", "game": "NE@NYJ", "player": "Drake Maye", "stat": "passingYards",
                            "side": "over", "line": 214.5}]


def test_a_tracker_failure_never_stops_the_logging(gh, tmp_path, monkeypatch):
    def boom(week):
        raise RuntimeError("schedule down")

    monkeypatch.setattr(bet_slip_bot, "tracker_context", boom)
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    bet_slip_bot.cmd_intake(5)
    cid = gh.add_comment(DAN, "confirm", comment_id=100)
    reply = tmp_path / "reply.md"
    bet_slip_bot.cmd_comment(5, cid, str(reply))
    assert "logged=true" in out.read_text() and "tracker=true" not in out.read_text()
    assert "couldn't be added to the live tracker" in reply.read_text()


def test_a_strangers_confirm_is_ignored(gh, tmp_path):
    bet_slip_bot.cmd_intake(5)
    cid = gh.add_comment(STRANGER, "confirm", comment_id=200)
    bet_slip_bot.cmd_comment(5, cid, str(tmp_path / "reply.md"))
    assert not (tmp_path / "reply.md").exists()
    assert len(gh.posted) == 1


def test_a_forged_draft_from_a_stranger_is_never_logged(gh, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    forged = bet_slips.normalize(PARSED, 4, None)
    forged["slips"][0]["stake_gbp"] = 9999.0
    gh.add_comment(STRANGER, bet_slips.render_draft_comment(forged))
    cid = gh.add_comment(DAN, "confirm", comment_id=300)
    bet_slip_bot.cmd_comment(5, cid, str(tmp_path / "reply.md"))
    assert "no draft to confirm" in gh.posted[-1]
    assert not bet_slip_bot._already_logged(5)


def test_a_correction_rereads_with_the_previous_draft(gh, tmp_path, monkeypatch):
    seen = {}

    def parse(images, **kw):
        seen.update(kw)
        return {**PARSED, "week": 5}

    bet_slip_bot.cmd_intake(5)
    monkeypatch.setattr(bet_slips, "parse_slip_images", parse)
    cid = gh.add_comment(DAN, "week is 5", comment_id=400)
    bet_slip_bot.cmd_comment(5, cid, str(tmp_path / "reply.md"))
    assert seen["correction"] == "week is 5"
    assert seen["previous"]["week"] == 4
    assert bet_slips.latest_draft(gh.comments)["week"] == 5


def test_cancel_before_logging_closes_as_not_planned(gh, tmp_path):
    bet_slip_bot.cmd_intake(5)
    cid = gh.add_comment(DAN, "cancel", comment_id=500)
    bet_slip_bot.cmd_comment(5, cid, str(tmp_path / "reply.md"))
    assert gh.closed == "not_planned"


def test_cancel_after_logging_removes_nothing(gh, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    bet_slip_bot.cmd_intake(5)
    bet_slip_bot.cmd_comment(5, gh.add_comment(DAN, "confirm", comment_id=600), str(tmp_path / "reply.md"))
    bet_slip_bot.cmd_comment(5, gh.add_comment(DAN, "cancel", comment_id=601), str(tmp_path / "reply2.md"))
    assert "already logged" in gh.posted[-1]
    assert gh.closed is None


def test_a_screenshot_posted_as_a_comment_is_read(gh, tmp_path):
    gh.issue["body_html"] = "<p>slip below</p>"
    bet_slip_bot.cmd_intake(5)
    assert "couldn't find a screenshot" in gh.posted[0]

    cid = gh.add_comment(DAN, "![slip](https://github.com/user-attachments/assets/xyz)", comment_id=700,
                         body_html='<p><img src="https://github.com/user-attachments/assets/xyz"></p>')
    bet_slip_bot.cmd_comment(5, cid, str(tmp_path / "reply.md"))
    assert gh.downloaded[-1] == ["https://github.com/user-attachments/assets/xyz"]
    assert bet_slips.latest_draft(gh.comments) is not None


def test_a_strangers_images_are_never_read(gh, tmp_path):
    gh.issue["body_html"] = "<p>no picture</p>"
    gh.add_comment(STRANGER, "![x](https://github.com/user-attachments/assets/evil)",
                   body_html='<img src="https://github.com/user-attachments/assets/evil">')
    cid = gh.add_comment(DAN, "retry", comment_id=800)
    bet_slip_bot.cmd_comment(5, cid, str(tmp_path / "reply.md"))
    assert gh.downloaded == []
    assert "couldn't find a screenshot" in gh.posted[-1]


def test_correction_text_excludes_image_markup(gh, tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(bet_slips, "parse_slip_images", lambda images, **kw: seen.update(kw) or PARSED)
    bet_slip_bot.cmd_intake(5)
    cid = gh.add_comment(DAN, "stake was £10 ![s](https://github.com/user-attachments/assets/2)", comment_id=900,
                         body_html='<p>stake was £10 <img src="https://github.com/user-attachments/assets/2"></p>')
    bet_slip_bot.cmd_comment(5, cid, str(tmp_path / "reply.md"))
    assert seen["correction"] == "stake was £10"
    assert "https://github.com/user-attachments/assets/2" in gh.downloaded[-1]


def test_confirm_refuses_when_a_correction_was_never_processed(gh, tmp_path, monkeypatch):
    # Simulates GitHub dropping the queued run for "stake was £10".
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    bet_slip_bot.cmd_intake(5)
    gh.add_comment(DAN, "stake was £10", comment_id=1000)
    cid = gh.add_comment(DAN, "confirm", comment_id=1001)
    bet_slip_bot.cmd_comment(5, cid, str(tmp_path / "reply.md"))
    assert "haven't processed" in gh.posted[-1]
    assert not bet_slip_bot._already_logged(5)


def test_confirm_goes_through_once_the_correction_has_a_new_draft(gh, tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    bet_slip_bot.cmd_intake(5)
    bet_slip_bot.cmd_comment(5, gh.add_comment(DAN, "stake was £10", comment_id=1100), str(tmp_path / "r1.md"))
    bet_slip_bot.cmd_comment(5, gh.add_comment(DAN, "confirm", comment_id=1101), str(tmp_path / "r2.md"))
    assert bet_slip_bot._already_logged(5)


def test_parse_failure_is_reported_not_swallowed(gh, monkeypatch):
    def fail(images, **kw):
        raise bet_slips.SlipParseError("Claude stopped early (stop_reason=max_tokens)")

    monkeypatch.setattr(bet_slips, "parse_slip_images", fail)
    bet_slip_bot.cmd_intake(5)
    assert "Reading the slip failed" in gh.posted[0] and "max_tokens" in gh.posted[0]


FOOTBALL = {
    "is_bet_slip": True, "week": None, "unclear": None,
    "slips": [{
        "sport": "football", "bet_type": "accumulator", "bookmaker": "Spreadex", "stake_gbp": 5.0,
        "total_odds": "4/1", "potential_returns_gbp": 25.0,
        "legs": [
            {"player": "", "team": None, "event": "Forfar Athletic v Spartans", "competition": "Scottish League Two",
             "match_date": None, "market_text": "Over 2.5 Goals", "market": "match_goals", "side": "over",
             "line": 2.5, "odds": "11/10", "bet_builder_group": None},
            {"player": "", "team": None, "event": "Stockport County v Bolton Wanderers", "competition": "League One",
             "match_date": "2026-11-21", "market_text": "Both Teams To Score", "market": "btts", "side": "yes",
             "line": None, "odds": "4/6", "bet_builder_group": None},
        ],
    }],
}


def test_a_football_slip_needs_no_nfl_week_and_goes_on_the_tracker_only(gh, tmp_path, monkeypatch):
    import json

    monkeypatch.setattr(bet_slips, "parse_slip_images", lambda images, **kw: FOOTBALL)
    monkeypatch.setattr(bet_slip_bot, "current_week", lambda: pytest.fail("NFL week looked up for a football slip"))
    monkeypatch.setattr(bet_slip_bot, "tracker_context", lambda week: pytest.fail("NFL schedule loaded"))
    gh.issue["created_at"] = "2026-11-21T09:30:00Z"
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))

    bet_slip_bot.cmd_intake(5)
    draft = bet_slips.latest_draft(gh.comments)
    assert "Week" not in gh.posted[0] and "NFL week" not in gh.posted[0]
    assert "assumed 2026-11-21" in gh.posted[0]
    assert [leg["date"] for leg in draft["slips"][0]["legs"]] == ["2026-11-21", "2026-11-21"]

    cid = gh.add_comment(DAN, "confirm", comment_id=100)
    reply = tmp_path / "reply.md"
    bet_slip_bot.cmd_comment(5, cid, str(reply))
    assert "logged=true" in out.read_text() and "tracker=true" in out.read_text()
    assert "Logged" not in reply.read_text() and "2 of 2 legs followed live" in reply.read_text()
    conn = sqlite3.connect(gh.db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM prop_bets").fetchone()[0] == 0
    except sqlite3.OperationalError:
        pass  # table never created: nothing logged, as intended
    bet = json.load(open(gh.bets_path))["bets"][0]
    assert bet["kind"] == "Football Accumulator" and bet["book"] == "Spreadex" and bet["dates"] == ["20261121"]
    assert bet["legs"][0] == {"sport": "soccer", "date": "20261121", "home": "Forfar Athletic", "away": "Spartans",
                              "league": "ls:sco4", "type": "goals", "side": "over", "line": 2.5}
    assert bet["legs"][1]["type"] == "btts" and bet["legs"][1]["league"] == "eng.3"
    assert "stake" not in bet and "returns" not in bet
    import csv
    rows = list(csv.DictReader(open(gh.prices_path)))
    assert [(r["issue"], r["game"], r["book_price"]) for r in rows] == [
        ("5", "Forfar Athletic v Spartans", "2.1"), ("5", "Stockport County v Bolton Wanderers", "1.6667")]
