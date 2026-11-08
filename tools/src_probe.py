import sys, json, requests
sys.path.insert(0, ".")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
URLS = [
 "https://site.api.espn.com/apis/site/v2/sports/cricket/scoreboard",
 "https://site.web.api.espn.com/apis/site/v2/sports/cricket/scorepanel",
 "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
 "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/current?lang=en&latest=true",
 "https://www.cricbuzz.com/api/cricket-match/live-matches",
 "https://www.espncricinfo.com/rss/livescores.xml",
 "https://static.cricinfo.com/rss/livescores.xml",
]
for u in URLS:
    try:
        r = requests.get(u, headers=H, timeout=30)
        print("\n###", u, r.status_code, r.headers.get("content-type"), len(r.text))
        print(r.text[:1500])
    except Exception as e:
        print("\n###", u, "ERR", e)
# follow ESPN cricket scoreboard deeper
try:
    j = requests.get(URLS[1], headers=H, timeout=30).json()
    for sc in (j.get("scores") or [])[:3]:
        lg = sc.get("leagues", [{}])[0]
        for ev in sc.get("events", [])[:3]:
            print("EV", lg.get("id"), lg.get("name"), ev.get("id"), ev.get("name"), ev.get("status", {}).get("type", {}).get("description"))
            s = requests.get(f"https://site.web.api.espn.com/apis/site/v2/sports/cricket/{lg.get('id')}/summary?event={ev.get('id')}", headers=H, timeout=30)
            print("SUMMARY", s.status_code, list(s.json().keys()) if s.ok else s.text[:200])
            if s.ok:
                d = s.json()
                print(json.dumps(d.get("header", {}))[:1500])
                print("ROSTERS", json.dumps(d.get("rosters", []))[:1500])
                print("NOTES", json.dumps(d.get("notes", d.get("article", {})))[:800])
            break
except Exception as e:
    print("deep ERR", e)
