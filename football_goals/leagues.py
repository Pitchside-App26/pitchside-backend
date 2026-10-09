"""The eleven leagues the report covers, and where each one's data comes from."""
from dataclasses import dataclass


@dataclass(frozen=True)
class League:
    key: str            # short id used in files and the history log
    name: str           # shown in the report
    teams: int          # expected number of clubs this season
    fd_code: str | None = None     # football-data.co.uk division code
    espn_slug: str | None = None   # ESPN league slug (fixture status + published table)
    odds_key: str | None = None    # The Odds API sport key, if it prices this league
    regional: str | None = None    # "north"/"south" for the National League regional divisions
    bbc_slug: str | None = None    # BBC Sport league page, used only for its published table
    livescore_stage: str | None = None  # LiveScore stage, a second results source for grading

    @property
    def max_meetings(self) -> int:
        """Times the same home-v-away pairing can occur in a season: once in
        England; twice in Scotland (4-round leagues, and the Premiership split)."""
        return 2 if self.key.startswith("SCO") else 1


LEAGUES = [
    League("ENG1", "Premier League", 20, "E0", "eng.1", "soccer_epl"),
    League("ENG2", "Championship", 24, "E1", "eng.2", "soccer_efl_champ"),
    League("ENG3", "League One", 24, "E2", "eng.3", "soccer_england_league1"),
    League("ENG4", "League Two", 24, "E3", "eng.4", "soccer_england_league2"),
    League("ENG5", "National League", 24, "EC", "eng.5"),
    League("ENG6N", "National League North", 24, regional="north", bbc_slug="national-league-north"),
    League("ENG6S", "National League South", 24, regional="south", bbc_slug="national-league-south"),
    League("SCO1", "Scottish Premiership", 12, "SC0", "sco.1", "soccer_spl"),
    League("SCO2", "Scottish Championship", 10, "SC1", "sco.2"),
    League("SCO3", "Scottish League One", 10, "SC2", bbc_slug="scottish-league-one", livescore_stage="sco3"),
    League("SCO4", "Scottish League Two", 10, "SC3", bbc_slug="scottish-league-two", livescore_stage="sco4"),
]

BY_KEY = {lg.key: lg for lg in LEAGUES}
BY_FD = {lg.fd_code: lg for lg in LEAGUES if lg.fd_code}
