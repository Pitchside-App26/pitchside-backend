import requests
r = requests.get("https://prod-public-api.livescore.com/v1/api/app/date/soccer/20261003/0", timeout=30,
                 headers={"User-Agent": "Mozilla/5.0"})
for st in r.json().get("Stages", []):
    if "Scot" in str(st.get("Cnm")) or "Scot" in str(st.get("Snm")):
        evs = st.get("Events", [])
        print(repr(st.get("Cnm")), "|", repr(st.get("Snm")), "|", len(evs),
              [(e["T1"][0]["Nm"], e["T2"][0]["Nm"], e.get("Tr1"), e.get("Tr2"), e.get("Trh1"), e.get("Trh2")) for e in evs[:2]])
