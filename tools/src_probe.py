import sys, json, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
B = "https://site.web.api.espn.com/apis/site/v2/sports/cricket"
j = requests.get(B + "/scorepanel", headers=H, timeout=30).json()
done = None
for sc in j.get("scores") or []:
    lg = sc.get("leagues", [{}])[0]
    for ev in sc.get("events", []):
        st = ev.get("status", {}).get("type", {})
        print("EV", lg.get("id"), lg.get("name")[:40], ev.get("id"), ev.get("name"), "|", st.get("description"), st.get("completed"), ev.get("date"))
        if st.get("completed") and not done:
            done = (lg.get("id"), ev.get("id"))
print("DONE", done)
d = requests.get(f"{B}/{done[0]}/summary?event={done[1]}", headers=H, timeout=30).json()
comp = d["header"]["competitions"][0]
print("STATUS", json.dumps(comp.get("status"))[:600])
for c in comp["competitors"]:
    print("COMP", json.dumps({k: c.get(k) for k in ("homeAway", "winner", "score", "linescores", "order")})[:1500])
    print("TEAM", c["team"].get("displayName"))
r0 = d["rosters"][0]
pl = r0["roster"][0]
print("PLAYERKEYS", list(pl.keys()))
print("PLAYER", json.dumps(pl)[:3000])
print("NOTES", json.dumps(d.get("notes"))[:1500])
print("LEADERS", json.dumps(d.get("leaders"))[:2000])
print("GAMEINFO", json.dumps(d.get("gameInfo"))[:500])
print("ARTICLE", json.dumps(d.get("article", {}))[:300])
# football
S = "https://site.api.espn.com/apis/site/v2/sports/soccer"
for lg in ["eng.1", "esp.1", "uefa.champions", "ksa.1"]:
    sb = requests.get(f"{S}/{lg}/scoreboard", headers=H, timeout=30).json()
    evs = sb.get("events", [])
    print("SOCCER", lg, len(evs), [(e["id"], e["name"], e["status"]["type"]["description"]) for e in evs[:4]])
sb = requests.get(f"{S}/eng.1/scoreboard", headers=H, timeout=30).json()
ev = next((e for e in sb["events"] if e["status"]["type"].get("completed")), None)
if ev:
    s = requests.get(f"{S}/eng.1/summary?event={ev['id']}", headers=H, timeout=30).json()
    print("SKEYS", list(s.keys()))
    print("KEYEVENTS", json.dumps(s.get("keyEvents", []))[:2500])
    print("BOX", json.dumps(s.get("boxscore", {}).get("teams", []))[:1200])
    print("VENUE", json.dumps(s.get("gameInfo", {}))[:300])
