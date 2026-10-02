"""Probe: which free sources serve National League North/South half-time
scores to a GitHub runner?"""
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept-Language": "en-GB,en;q=0.9"}
DAY = "2026-09-26"


def get(url, **kw):
    try:
        r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=30, **kw)
        print(f"  {r.status_code} {len(r.content):>8}B {url}")
        return r
    except Exception as e:  # noqa: BLE001
        print("  ERROR", url, type(e).__name__, e)


def initial_data(html):
    m = re.search(r'window\.__INITIAL_DATA__\s*=\s*("(?:[^"\\]|\\.)*")', html)
    return json.loads(json.loads(m.group(1))) if m else None


print("=== BBC results list + one match page ===")
for slug in ["national-league-north", "national-league-south"]:
    r = get(f"https://www.bbc.co.uk/sport/football/{slug}/scores-fixtures/{DAY[:7]}")
    if r is None or r.status_code != 200:
        continue
    s = r.text
    data = initial_data(s)
    blob = json.dumps(data) if data else s
    for kw in ["halfTime", "HT", "periods", "firstHalf", "half"]:
        print(f"   '{kw}' count:", blob.count(kw))
    links = sorted(set(re.findall(r'/sport/football/live/[a-z0-9]+|/sport/football/\d{6,}', blob)))
    print("   match links:", len(links), links[:3])
    if links:
        r2 = get("https://www.bbc.co.uk" + links[0])
        if r2 is not None and r2.status_code == 200:
            d2 = initial_data(r2.text)
            b2 = json.dumps(d2) if d2 else r2.text
            for kw in ["halfTime", "HT", "Half Time", "periods", "firstHalf"]:
                i = b2.find(kw)
                print(f"   match page '{kw}':", b2.count(kw), b2[max(0, i - 150):i + 150].replace("\n", " ") if i >= 0 else "")
    # first event object in the list, to see what fields BBC carries per match
    i = blob.find('"homeTeam"')
    print("   event sample:", blob[max(0, i - 400):i + 900] if i >= 0 else "none")

print("\n=== Sofascore ===")
for base in ["https://api.sofascore.com", "https://www.sofascore.com"]:
    r = get(f"{base}/api/v1/sport/football/scheduled-events/{DAY}")
    if r is not None and r.status_code == 200:
        evs = [e for e in r.json().get("events", []) if "National League" in e["tournament"]["name"]]
        print("   NL events:", len(evs))
        for e in evs[:3]:
            print("   ", e["tournament"]["name"], "|", e["homeTeam"]["name"], e["homeScore"].get("current"),
                  "-", e["awayScore"].get("current"), e["awayTeam"]["name"],
                  "| HT", e["homeScore"].get("period1"), "-", e["awayScore"].get("period1"))
        break

print("\n=== LiveScore public API ===")
r = get(f"https://prod-public-api.livescore.com/v1/api/app/date/soccer/{DAY.replace('-', '')}/0")
if r is not None and r.status_code == 200:
    for st in r.json().get("Stages", []):
        if "National League" in st.get("Snm", "") or "National League" in st.get("CompN", ""):
            evs = st.get("Events", [])
            print("   stage:", st.get("Snm"), st.get("Cnm"), "events:", len(evs))
            if evs:
                e = evs[0]
                print("   sample keys:", sorted(e.keys()))
                print("   ", e["T1"][0]["Nm"], e.get("Tr1"), "-", e.get("Tr2"), e["T2"][0]["Nm"],
                      "| HT", e.get("Trh1"), "-", e.get("Trh2"), "| status", e.get("Eps"))

print("\n=== FotMob ===")
r = get(f"https://www.fotmob.com/api/data/matches?date={DAY.replace('-', '')}")
if r is not None and r.status_code == 200:
    for lg in r.json().get("leagues", []):
        if "National League" in lg.get("name", ""):
            print("   ", lg["name"], lg.get("ccode"), "matches:", len(lg.get("matches", [])),
                  "sample:", json.dumps(lg["matches"][0])[:400] if lg.get("matches") else "")

print("\n=== Flashscore ===")
get("https://www.flashscore.co.uk/football/england/national-league-north/results/")
r = get("https://local-global.flashscore.ninja/2/x/feed/f_1_-6_3_en-uk_1", headers={"x-fsign": "SW9D1eZo"})
if r is not None and r.status_code == 200:
    t = r.text
    print("   'National League North' in feed:", "National League North" in t, "| len", len(t))
