import json

import pytest

from projection_engine import Projection
from rank_props import build_ranked_prop
from output import to_json_records


def _proj():
    return Projection(
        player_id="p1", player_name="Test Player", stat_col="yards",
        projection=80.0, season_std=10.0, n_current_games=5, n_prior_games=0,
        method="veteran", confidence="normal",
    )


def test_json_records_are_actually_valid_json_with_a_one_sided_price():
    # Reproduces a real failure: a prop where only ONE side's price was
    # recorded (e.g. a book quotes Over but not Under) arrives here as
    # float('nan') for the missing side, not None -- that's what a pandas
    # row.get() on a column with no value for that row returns. Before the
    # fix, this NaN sailed through pricing.py's math unchecked and
    # json.dump() wrote a literal `NaN` token, which is valid Python but
    # NOT valid JSON -- the live site's fetch().json() failed to parse the
    # whole file over one bad field.
    ranked = build_ranked_prop(
        _proj(), line=70.0, current_season_values=[],
        over_price=-115.0, under_price=float("nan"),
    )
    payload = {"season": 2026, "week": 1, "props": to_json_records([ranked])}
    text = json.dumps(payload)  # must not raise, and must not contain a bare NaN
    assert "NaN" not in text
    reparsed = json.loads(text)  # the real assertion: a browser's JSON.parse would accept this
    assert reparsed["props"][0]["price"] == -115.0


def test_json_dump_with_allow_nan_false_rejects_any_stray_nan():
    # Belt-and-suspenders: this is the actual guarantee write_json relies
    # on. Even if some future field leaks a real NaN past _clean,
    # allow_nan=False makes generation fail loudly right here in CI logs,
    # instead of silently publishing invalid JSON to the live page again.
    with pytest.raises(ValueError):
        json.dumps({"value": float("nan")}, allow_nan=False)
