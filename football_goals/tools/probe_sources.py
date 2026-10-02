"""Coverage probe, round 3: National League North/South sources with half-time
scores, ESPN Scottish coverage, and whether The Odds API prices Over 1.5."""
import json
import os
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def get(url, **kw):
    try:
        return requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=30, **kw)
    except Exception as e:  # noqa: BLE001
        print("  ERROR", url, e)


print("=== ESPN past-date coverage ===")
for slug in ["eng.1", "eng.2", "sco.1", "sco.2", "sco.3", "sco.4"]:
    for d in ["20260926", "20260927", "20260919", "20260920"]:
        r = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={d}")
        if r is not None and r.status_code == 200:
            evs = r.json().get("events", [])
            print(slug, d, "events:", len(evs), [e["status"]["type"]["name"] for e in evs][:3])
r = get("https://site.api.espn.com/apis/site/v2/sports/soccer/eng.5/scoreboard?dates=20260801-20261002")
if r is not None and r.status_code == 200:
    print("eng.5 date-range query events:", len(r.json().get("events", [])))

print("\n=== worldfootball.net ===")
for u in ["https://www.worldfootball.net/all_matches/eng-national-league-north-2026-2027/",
          "https://www.worldfootball.net/all_matches/eng-national-league-south-2026-2027/",
          "https://www.worldfootball.net/all_matches/eng-national-league-2026-2027/"]:
    r = get(u)
    if r is not None:
        txt = r.text
        print(u, r.status_code, "final:", r.url, "bytes:", len(txt))
        print("   title:", re.search(r"<title>(.*?)</title>", txt, re.S).group(1).strip() if "<title>" in txt else None)
        print("   score samples:", re.findall(r"\d+:\d+ \(\d+:\d+\)", txt)[:5])

print("\n=== BBC ===")
r = get("https://www.bbc.co.uk/sport/football/national-league-north/scores-fixtures/2026-09")
if r is not None:
    txt = r.text
    print("status", r.status_code, "bytes", len(txt))
    for kw in ["halfTime", "HT", "periods", "postponed", "Postponed", "__INITIAL_DATA__", "eventStatus"]:
        print("  contains", kw, txt.count(kw))
    i = txt.find("halfTime")
    print("  ctx:", txt[i - 200:i + 200] if i > 0 else None)

print("\n=== SoccerSTATS ===")
for u in ["https://www.soccerstats.com/latest.asp?league=england6",
          "https://www.soccerstats.com/latest.asp?league=england7",
          "https://www.soccerstats.com/results.asp?league=england6&pmtype=bydate"]:
    r = get(u)
    if r is not None:
        txt = r.text
        title = re.search(r"<title>(.*?)</title>", txt, re.S)
        print(u, r.status_code, "final:", r.url, "title:", title and title.group(1).strip()[:100])
        print("   HT samples:", re.findall(r"\(\d+-\d+\)", txt)[:5], "mentions North:", txt.count("North"), "South:", txt.count("South"))

print("\n=== API-Football public docs: free plan seasons ===")
r = get("https://www.api-football.com/pricing")
if r is not None:
    t = re.sub(r"<[^>]+>", " ", r.text)
    t = re.sub(r"\s+", " ", t)
    for kw in ["Free", "season", "Seasons", "$"]:
        for m in re.finditer(re.escape(kw), t):
            print("  ...", t[max(0, m.start() - 120):m.start() + 160])
            break

print("\n=== The Odds API: Over 1.5 availability (2 credits) ===")
key = os.environ.get("ODDS_API_KEY")
if key:
    r = get("https://api.the-odds-api.com/v4/sports/soccer_england_league2/events", params={"apiKey": key})
    evs = r.json() if r is not None and r.status_code == 200 else []
    print("league2 events (free call):", len(evs))
    if evs:
        eid = evs[0]["id"]
        r = get(f"https://api.the-odds-api.com/v4/sports/soccer_england_league2/events/{eid}/odds",
                params={"apiKey": key, "regions": "uk", "markets": "alternate_totals", "oddsFormat": "decimal"})
        if r is not None:
            print("alternate_totals HTTP", r.status_code, r.text[:300] if r.status_code != 200 else "")
            if r.status_code == 200:
                pts = sorted({o.get("point") for b in r.json().get("bookmakers", []) for m in b["markets"] for o in m["outcomes"]})
                print("  alt points:", pts, "bookmakers:", [b["key"] for b in r.json().get("bookmakers", [])])
            print("quota remaining:", r.headers.get("x-requests-remaining"))
