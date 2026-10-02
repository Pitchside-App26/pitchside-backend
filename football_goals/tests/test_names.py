from football_goals.names import best_match

E2 = ["AFC Wimbledon", "Barnsley", "Milton Keynes Dons", "Peterboro", "Sheffield Weds", "Stockport",
      "Leyton Orient", "Bradford", "Reading", "Burton", "Huddersfield", "Plymouth"]


def test_espn_names_map_to_football_data():
    assert best_match("Peterborough United", E2) == "Peterboro"
    assert best_match("Sheffield Wednesday", E2) == "Sheffield Weds"
    assert best_match("Bradford City", E2) == "Bradford"
    assert best_match("Burton Albion", E2) == "Burton"
    assert best_match("Huddersfield Town", E2) == "Huddersfield"
    assert best_match("Plymouth Argyle", E2) == "Plymouth"
    assert best_match("Stockport County", E2) == "Stockport"
    assert best_match("AFC Wimbledon", E2) == "AFC Wimbledon"


def test_similar_clubs_kept_apart():
    pl = ["Man City", "Man United", "Nott'm Forest", "Newcastle"]
    assert best_match("Manchester City", pl) == "Man City"
    assert best_match("Manchester United", pl) == "Man United"
    assert best_match("Nottingham Forest", pl) == "Nott'm Forest"
    sco = ["Dundee", "Dundee United", "Queens Park", "Queen of Sth", "Inverness C"]
    assert best_match("Dundee United", sco) == "Dundee United"
    assert best_match("Dundee", sco) == "Dundee"
    assert best_match("Queen of the South", sco) == "Queen of Sth"
    assert best_match("Queen's Park", sco) == "Queens Park"
    assert best_match("Inverness Caledonian Thistle", sco) == "Inverness C"


def test_unknown_club_is_none():
    assert best_match("Real Madrid", E2) is None
