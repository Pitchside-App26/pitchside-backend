import json

from football_goals.sources.bbc import parse_table


def test_parse_embedded_table():
    data = {"page": {"modules": [{"tables": [{"rows": [
        {"name": "Alloa Athletic", "matchesPlayed": 8, "goalsScoredFor": 8, "goalsScoredAgainst": 6, "points": 9},
        {"name": "East Kilbride", "matchesPlayed": 8, "goalsScoredFor": 14, "goalsScoredAgainst": 12},
    ]}]}]}}
    html = "<script>window.__INITIAL_DATA__=" + json.dumps(json.dumps(data)) + ";</script>"
    t = parse_table(html)
    assert t == {"Alloa Athletic": {"gp": 8, "gf": 8, "ga": 6}, "East Kilbride": {"gp": 8, "gf": 14, "ga": 12}}
