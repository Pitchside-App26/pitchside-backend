"""Weekly injury report -- whether a player is even expected to play, which
nothing in this engine checked before. Found while reviewing what facets
the model has a concept of: a player ruled OUT still got ranked as a live
prop with no signal that the prop was effectively dead.

CONFIRMED against real 2026 week 1 data: nfl_data_py.import_injuries()
returns exactly one row per (gsis_id, week) -- already the week's final
report, not a per-practice-day log that would need deduplicating. Real
report_status values seen: "Out", "Doubtful", "Questionable", and None
(not on the injury report at all, i.e. no concern).
"""
import logging

import nfl_data_py as nfl
import pandas as pd

logger = logging.getLogger(__name__)


def fetch_injury_report(season: int, week: int) -> dict[str, str]:
    """{gsis_id: report_status} for players who ARE on that week's injury
    report ("Out" | "Doubtful" | "Questionable") -- players not present in
    the returned dict simply aren't on the report, which is the normal
    case and not itself meaningful.
    """
    try:
        injuries = nfl.import_injuries([season])
    except Exception as exc:
        logger.warning("Could not fetch injury report for season %s (%s) -- skipping.", season, exc)
        return {}

    wk = injuries[(injuries["week"] == week) & injuries["report_status"].notna()]
    return dict(zip(wk["gsis_id"], wk["report_status"]))
