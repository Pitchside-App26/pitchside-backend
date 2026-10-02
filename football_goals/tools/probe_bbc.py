import json, re, requests
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128 Safari/537.36"}
for slug in ["scottish-league-one", "national-league-north"]:
    r = requests.get(f"https://www.bbc.co.uk/sport/football/{slug}/table", headers=UA, timeout=30)
    t = r.text
    print(slug, r.status_code, len(t))
    m = re.search(r'window\.__INITIAL_DATA__\s*=\s*("(?:[^"\\]|\\.)*")', t)
    if m:
        data = json.loads(json.loads(m.group(1)))
        def walk(o, path="", depth=0):
            if depth > 7: return
            if isinstance(o, dict):
                for k, v in o.items():
                    if k.lower() in ("played", "gamesplayed", "goalsfor", "goalsscored"):
                        print("  KEY", path + "/" + k, "=", str(v)[:80]); return
                    walk(v, path + "/" + k, depth + 1)
            elif isinstance(o, list) and o:
                walk(o[0], path + "[0]", depth + 1)
        walk(data)
        s = json.dumps(data)
        i = s.find("Alloa") if slug.startswith("scot") else s.find("Chester")
        print("  CTX:", s[max(0, i - 900): i + 1100])
    else:
        print("  no __INITIAL_DATA__ string; snippet:", t[t.find("Played") - 300: t.find("Played") + 500] if "Played" in t else "none")
        for tbl in re.findall(r"<table.*?</table>", t, re.S)[:1]:
            print("  TABLE:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", tbl))[:1500])
