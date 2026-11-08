import json, requests
H = {"User-Agent": "Mozilla/5.0"}
B = "https://site.api.espn.com/apis/site/v2/sports"
for path in ["racing/f1", "tennis/atp", "tennis/wta", "basketball/nba", "mma/ufc", "rugby/164205", "football/nfl"]:
    try:
        j = requests.get(f"{B}/{path}/scoreboard", headers=H, timeout=30).json()
        evs = j.get("events") or []
        print("\n###", path, len(evs))
        if evs:
            e = evs[0]
            print("EV", json.dumps({k: e.get(k) for k in ("id", "name", "date", "status")})[:600])
            comps = e.get("competitions") or []
            print("NCOMPS", len(comps), "GROUPINGS", len(e.get("groupings") or []))
            c = comps[-1] if comps else ((e.get("groupings") or [{}])[0].get("competitions") or [{}])[0]
            print("COMP", json.dumps({k: c.get(k) for k in ("id", "type", "status", "date")})[:500])
            for cp in (c.get("competitors") or [])[:3]:
                print("CP", json.dumps(cp)[:900])
            if path == "basketball/nba":
                s = requests.get(f"{B}/{path}/summary?event={e['id']}", headers=H, timeout=30).json()
                print("NBA LEADERS", json.dumps(s.get("leaders"))[:1500])
    except Exception as ex:
        print("ERR", path, ex)
