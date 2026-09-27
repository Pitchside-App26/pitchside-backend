import sqlite3

import pytest

from prop_bets_log import line_clv, log_placed_legs, record_closing_snapshot, settle_week


def _leg(player, market="player_pass_yds", side="over", book_line=214.5, book_price=1.9, **extra):
    leg = {"player": player, "market": market, "side": side, "book_line": book_line, "book_price": book_price}
    leg.update(extra)
    return leg


def test_log_placed_legs_inserts_rows(tmp_path):
    db_path = str(tmp_path / "test.sqlite3")
    n = log_placed_legs([_leg("Drake Maye"), _leg("Garrett Wilson", book_line=65.5)], week=4, acca_id="acca1", db_path=db_path)
    assert n == 2

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT player, week, acca_id, result FROM prop_bets ORDER BY player").fetchall()
    conn.close()
    assert rows == [("Drake Maye", 4, "acca1", None), ("Garrett Wilson", 4, "acca1", None)]


def test_record_closing_snapshot_only_updates_matches(tmp_path):
    db_path = str(tmp_path / "test.sqlite3")
    log_placed_legs([_leg("Drake Maye"), _leg("Garrett Wilson", book_line=65.5)], week=4, acca_id="a1", db_path=db_path)

    updated = record_closing_snapshot(
        4, {("Drake Maye", "player_pass_yds"): (220.0, 0.55)}, db_path=db_path,
    )
    assert updated == 1

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT closing_consensus_line, closing_fair_prob FROM prop_bets WHERE player='Drake Maye'"
    ).fetchone()
    other = conn.execute(
        "SELECT closing_consensus_line FROM prop_bets WHERE player='Garrett Wilson'"
    ).fetchone()
    conn.close()
    assert row == (220.0, 0.55)
    assert other == (None,)


def test_settle_week_win_loss_push_and_void(tmp_path):
    db_path = str(tmp_path / "test.sqlite3")
    log_placed_legs([
        _leg("Winner", book_line=200.0),   # over 200, actual 250 -> win
        _leg("Loser", book_line=200.0),    # over 200, actual 150 -> loss
        _leg("Pusher", book_line=200.0),   # over 200, actual 200.0 -> push
        _leg("DidNotPlay", book_line=200.0),  # actual=None -> void
    ], week=4, acca_id="a1", db_path=db_path)

    count = settle_week(4, {
        ("Winner", "player_pass_yds"): 250.0,
        ("Loser", "player_pass_yds"): 150.0,
        ("Pusher", "player_pass_yds"): 200.0,
        ("DidNotPlay", "player_pass_yds"): None,
    }, db_path=db_path)
    assert count == 4

    conn = sqlite3.connect(db_path)
    results = dict(conn.execute("SELECT player, result FROM prop_bets").fetchall())
    conn.close()
    assert results == {"Winner": "win", "Loser": "loss", "Pusher": "push", "DidNotPlay": "void"}


def test_settle_week_leaves_unfinished_games_unsettled(tmp_path):
    db_path = str(tmp_path / "test.sqlite3")
    log_placed_legs([_leg("StillPlaying")], week=4, acca_id="a1", db_path=db_path)

    count = settle_week(4, {}, db_path=db_path)  # no actuals yet -- game hasn't finished
    assert count == 0

    conn = sqlite3.connect(db_path)
    result = conn.execute("SELECT result FROM prop_bets WHERE player='StillPlaying'").fetchone()
    conn.close()
    assert result == (None,)


def test_settle_week_never_resettles_a_graded_leg(tmp_path):
    db_path = str(tmp_path / "test.sqlite3")
    log_placed_legs([_leg("Winner", book_line=200.0)], week=4, acca_id="a1", db_path=db_path)
    settle_week(4, {("Winner", "player_pass_yds"): 250.0}, db_path=db_path)

    # A second settle call with a DIFFERENT (wrong) actual must not overwrite the first result
    count = settle_week(4, {("Winner", "player_pass_yds"): 50.0}, db_path=db_path)
    assert count == 0

    conn = sqlite3.connect(db_path)
    result, actual = conn.execute("SELECT result, actual_stat FROM prop_bets WHERE player='Winner'").fetchone()
    conn.close()
    assert result == "win"
    assert actual == 250.0


def test_line_clv_positive_means_beat_the_close():
    assert line_clv(book_line=214.5, closing_consensus_line=220.0) == pytest.approx(5.5)


def test_line_clv_negative_means_worse_than_close():
    assert line_clv(book_line=222.5, closing_consensus_line=214.5) == pytest.approx(-8.0)


def test_line_clv_none_without_closing_line():
    assert line_clv(book_line=214.5, closing_consensus_line=None) is None
