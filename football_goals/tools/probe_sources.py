"""One-off coverage probe: checks what each candidate data source actually
serves for this season, so source choices rest on evidence, not memory.
Run from GitHub Actions (the dev sandbox can't reach these hosts)."""
import io
import json
import os

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (pitchside football_goals probe)"}
DATE = os.environ.get("PROBE_DATE", "2026-10-03")


def get(url, **kw):
    try:
        r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=30, **kw)
        return r
    except Exception as e:  # noqa: BLE001
        print(f"  ERROR {url}: {e}")
        return None


SKIP_RESULTS = True
print("=== football-data.co.uk results, season 2627 ===")
for code in ([] if SKIP_RESULTS else ["E0", "E1", "E2", "E3", "EC", "SC0", "SC1", "SC2", "SC3"]):
    url = f"https://www.football-data.co.uk/mmz4281/2627/{code}.csv"
    r = get(url)
    if r is None or r.status_code != 200:
        print(code, "HTTP", r and r.status_code)
        continue
    df = pd.read_csv(io.StringIO(r.content.decode("latin-1").lstrip("\xef\xbb\xbf").lstrip("\ufeff")))
    df = df.dropna(how="all")
    teams = sorted(set(df.HomeTeam.dropna()) | set(df.AwayTeam.dropna()))
    ht_ok = {"HTHG", "HTAG"} <= set(df.columns)
    ht_missing = int(df[["HTHG", "HTAG"]].isna().any(axis=1).sum()) if ht_ok else None
    print(f"{code}: rows={len(df)} teams={len(teams)} HT cols={ht_ok} HT missing rows={ht_missing} "
          f"last date={df.Date.iloc[-1]} last-modified={r.headers.get('Last-Modified')}")
    print("   teams:", ", ".join(teams))
    print("   cols:", ",".join(list(df.columns)[:12]))

print("\n=== football-data.co.uk fixtures.csv ===")
r = get("https://www.football-data.co.uk/fixtures.csv")
if r is not None and r.status_code == 200:
    fx = pd.read_csv(io.StringIO(r.content.decode("latin-1").lstrip("\xef\xbb\xbf").lstrip("\ufeff")))
    print("cols:", ",".join(list(fx.columns)[:10]), "last-modified:", r.headers.get("Last-Modified"))
    print("divs:", fx.Div.value_counts().to_dict())
    print("dates:", fx.Date.value_counts().to_dict())
    print(fx[fx.Div.isin(["E0","E1","E2","E3","EC","SC0","SC1","SC2","SC3"])][["Div","Date","Time","HomeTeam","AwayTeam"]].to_string())
else:
    print("fixtures HTTP", r and r.status_code)

print("\n=== ESPN scoreboard", DATE, "===")
d = DATE.replace("-", "")
for slug in ["eng.1", "eng.2", "eng.3", "eng.4", "eng.5", "eng.6", "eng.7", "eng.n_league_north",
             "eng.n_league_south", "sco.1", "sco.2", "sco.3", "sco.4"]:
    r = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={d}")
    if r is None or r.status_code != 200:
        print(slug, "HTTP", r and r.status_code)
        continue
    j = r.json()
    lg = (j.get("leagues") or [{}])[0].get("name")
    ev = j.get("events", [])
    st = {}
    for e in ev:
        s = e["status"]["type"]["name"]
        st[s] = st.get(s, 0) + 1
    print(f"{slug}: league={lg!r} events={len(ev)} statuses={st}")
    for e in ev[:2]:
        print("    ", e.get("name"), e.get("date"))
# does ESPN give half-time scores for completed games? check one past event's summary
r = get("https://site.api.espn.com/apis/site/v2/sports/soccer/eng.5/scoreboard?dates=20260926")
if r is not None and r.status_code == 200 and r.json().get("events"):
    e = r.json()["events"][0]
    comp = e["competitions"][0]
    print("eng.5 sample:", e["name"], [c.get("score") for c in comp["competitors"]],
          "linescores:", [c.get("linescores") for c in comp["competitors"]])

for slug, d2 in [("eng.1", "20260927"), ("eng.5", "20260929"), ("sco.1", "20260927")]:
    r = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={d2}")
    if r is not None and r.status_code == 200:
        evs = r.json().get("events", [])
        print(slug, d2, "completed events:", len(evs), [e["name"] + " " + "-".join(c.get("score","?") for c in e["competitions"][0]["competitors"]) for e in evs[:3]])
        if evs:
            eid = evs[0]["id"]
            r2 = get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/summary?event={eid}")
            if r2 is not None and r2.status_code == 200:
                j2 = r2.json()
                comp = j2.get("header", {}).get("competitions", [{}])[0]
                print("   summary linescores:", [(c.get("homeAway"), c.get("score"), c.get("linescores")) for c in comp.get("competitors", [])])
                ke = j2.get("keyEvents") or []
                print("   keyEvents goals:", [(k.get("type",{}).get("text"), k.get("clock",{}).get("displayValue"), k.get("period",{}).get("number")) for k in ke if k.get("scoringPlay")][:6])

print("\n=== API-Football ===")
key = os.environ.get("API_FOOTBALL_KEY")
if not key:
    print("API_FOOTBALL_KEY secret not set -- skipping")
else:
    h = {"x-apisports-key": key}
    base = "https://v3.football.api-sports.io"
    r = get(f"{base}/status", headers=h)
    print("status:", r and r.text[:400])
    for lid in [43, 50, 51]:
        r = get(f"{base}/fixtures", headers=h, params={"league": lid, "season": 2026})
        if r is not None:
            j = r.json()
            print(lid, "errors:", j.get("errors"), "results:", j.get("results"))

print("\n=== The Odds API ===")
key = os.environ.get("ODDS_API_KEY")
if not key:
    print("ODDS_API_KEY secret not set")
else:
    r = get("https://api.the-odds-api.com/v4/sports", params={"apiKey": key, "all": "true"})
    if r is not None and r.status_code == 200:
        for s in r.json():
            if s["key"].startswith(("soccer_england", "soccer_efl", "soccer_epl", "soccer_fa", "soccer_scotland", "soccer_spl")):
                print("  ", s["key"], "|", s["title"], "| active:", s["active"])
        print("quota remaining:", r.headers.get("x-requests-remaining"))
    else:
        print("sports HTTP", r and r.status_code, r and r.text[:200])
    # one paid call (1 credit): do totals on the EFL Championship include a 1.5 line?
    r = get("https://api.the-odds-api.com/v4/sports/soccer_efl_champ/odds",
            params={"apiKey": key, "regions": "uk", "markets": "totals", "oddsFormat": "decimal"})
    if r is not None and r.status_code == 200:
        pts = set()
        for ev in r.json():
            for bk in ev.get("bookmakers", []):
                for m in bk.get("markets", []):
                    for o in m.get("outcomes", []):
                        pts.add(o.get("point"))
        print("champ totals events:", len(r.json()), "points offered:", sorted(p for p in pts if p is not None))
        print("quota remaining:", r.headers.get("x-requests-remaining"))
    else:
        print("champ totals HTTP", r and r.status_code, r and r.text[:200])

print("\n=== Other free candidates (status only) ===")
for u in ["https://www.soccerstats.com/latest.asp?league=england6",
          "https://www.soccerstats.com/latest.asp?league=england7",
          "https://www.fotmob.com/api/leagues?id=9084",
          "https://www.bbc.co.uk/sport/football/national-league-north/scores-fixtures",
          "https://www.thesportsdb.com/api/v1/json/3/search_all_leagues.php?c=England&s=Soccer"]:
    r = get(u, allow_redirects=True)
    if r is not None:
        print(u, "->", r.status_code, "final:", r.url, "bytes:", len(r.content))
r = get("https://www.thesportsdb.com/api/v1/json/3/search_all_leagues.php?c=England&s=Soccer")
if r is not None and r.status_code == 200:
    for lg in (r.json().get("countries") or []):
        if "National" in lg.get("strLeague", ""):
            print("  TheSportsDB:", lg["idLeague"], lg["strLeague"])
