"""
Sports Hubs - MATCH RECAP reel (asli match data se), English + Urdu.

Cricket : toss -> 1st innings (score, top batsmen, top bowlers) -> 2nd innings -> natija
Football: natija -> pehla half (goals, minute, scorer) -> doosra half -> stats (possession, shots)

- Data: ESPN ka khula scoreboard/summary JSON (asli scorecard) - koi number AI apni taraf se nahi likhta.
- Tasveerein: players / stadium ki ASLI free photos (Wikipedia Commons), warna asli stock footage.
- Broadcaster ki match video (ICC/PCB/Premier League) NAHI - copyright strike se page ki monetization khatam hoti hai.
- Score har scene par screen par (lower-third), awaaz pehle second se.

Env: LANGUAGE (en/ur), SPORTS_PAGE_TOKEN/ID, SPORTS_GEMINI_API_KEY / GROQ_API_KEY, DRY_RUN
"""
import datetime
import json
import os
import re
import sys

os.environ["KIND"] = "reel"
os.environ["PAGES"] = "sports"

import requests            # noqa: E402

import news                # noqa: E402
import news_video as nv    # noqa: E402

LANG = news.LANG
DRY_RUN = news.DRY_RUN
HIST_FILE = "match_history.json"
REPORT_FILE = f"match_{LANG}_last_run.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
CRIC = "https://site.web.api.espn.com/apis/site/v2/sports/cricket"
SOC = "https://site.api.espn.com/apis/site/v2/sports/soccer"
SOC_LEAGUES = {"uefa.champions": 9, "eng.1": 9, "esp.1": 8, "ita.1": 6, "ger.1": 6, "fra.1": 5, "ksa.1": 6,
               "usa.1": 5, "uefa.europa": 4, "fifa.world": 14, "fifa.worldq.afc": 4, "fifa.worldq.uefa": 4,
               "fifa.friendly": 3, "eng.fa": 4, "esp.copa_del_rey": 3,
               # world cup / bare tournament - jab chalein to sab se upar
               "fifa.wwc": 9, "fifa.cwc": 9, "uefa.euro": 10, "conmebol.america": 9, "caf.nations": 8,
               "afc.asian.cup": 8, "concacaf.gold": 6, "fifa.worldq.conmebol": 5, "fifa.worldq.caf": 4,
               "fifa.olympics": 8}
BIG_CLUBS = {"real madrid", "barcelona", "manchester united", "manchester city", "liverpool", "arsenal", "chelsea",
             "bayern munich", "paris saint-germain", "juventus", "inter milan", "ac milan", "al nassr", "al hilal",
             "inter miami", "tottenham hotspur", "atletico madrid", "borussia dortmund", "napoli", "al ittihad"}
CRIC_TEAMS = {"pakistan": 10, "india": 9, "australia": 7, "england": 7, "south africa": 6, "new zealand": 6,
              "sri lanka": 6, "bangladesh": 6, "afghanistan": 6, "west indies": 5, "zimbabwe": 4, "ireland": 4}
CRIC_LEAGUES = ("pakistan super league", "indian premier league", "big bash", "t10", "the hundred", "sa20",
                "caribbean premier", "international league t20", "bangladesh premier", "lanka premier",
                "world cup", "champions trophy", "asia cup")

REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "lang": LANG, "dry_run": DRY_RUN,
          "posted": {}, "errors": []}
log = news.log


def get(url):
    r = requests.get(url, headers=UA, timeout=40)
    r.raise_for_status()
    return r.json()


def load_hist():
    try:
        with open(HIST_FILE, encoding="utf-8") as f:
            h = json.load(f)
    except Exception:
        h = {}
    h.setdefault("matches", [])
    h.setdefault("used_clips", [])
    return h


def age_h(iso):
    try:
        d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.datetime.now(datetime.timezone.utc) - d).total_seconds() / 3600
    except Exception:
        return 99


# ---------------------------------------------------------------- cricket
def num(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def stat_map(ls):
    out = {}
    for cat in ((ls.get("statistics") or {}).get("categories") or []):
        for s in cat.get("stats") or []:
            out[s.get("name")] = s.get("value") if s.get("value") not in (None, "") else s.get("displayValue")
    return out


def cricket_candidates(done):
    out = []
    j = get(CRIC + "/scorepanel")
    for sc in j.get("scores") or []:
        lg = (sc.get("leagues") or [{}])[0]
        lname = (lg.get("name") or "").lower()
        for ev in sc.get("events") or []:
            st = (ev.get("status") or {}).get("type") or {}
            if st.get("state") != "post" or st.get("description") != "Result" or f"c{ev['id']}" in done:
                continue
            if "women" in lname or "under-19" in lname or "u19" in lname:
                continue
            name = (ev.get("name") or "").lower()
            if " a v " in name + " " or name.endswith(" a") or "region" in name or "division" in name:
                continue
            score = max([v for t, v in CRIC_TEAMS.items() if re.search(rf"\b{t}\b(?! a\b| women| under)", name)] or [0])
            if any(k in lname for k in CRIC_LEAGUES):
                score += 6
            if "world cup" in lname or "champions trophy" in lname:
                score += 8
            if score <= 0:
                continue
            out.append({"sport": "cricket", "league": lg.get("id"), "lname": lg.get("name"), "id": ev["id"],
                        "name": ev.get("name"), "score": score + (12 if LANG == "ur" else 4)})
    return out


def cricket_facts(c):
    d = get(f"{CRIC}/{c['league']}/summary?event={c['id']}")
    comp = d["header"]["competitions"][0]
    teams = {}
    inns = []
    for t in comp["competitors"]:
        tn = t["team"]["displayName"]
        teams[t["team"]["id"]] = tn
        for ls in t.get("linescores") or []:
            if ls.get("isBatting") and (ls.get("runs") or ls.get("overs")):
                inns.append({"period": ls.get("period"), "team": tn, "tid": t["team"]["id"], "runs": int(num(ls.get("runs"))),
                             "wickets": int(num(ls.get("wickets"))), "overs": ls.get("overs"),
                             "fours": ls.get("fours"), "sixes": ls.get("sixes"), "target": ls.get("target") or None,
                             "winner": str(t.get("winner")).lower() == "true"})
    inns.sort(key=lambda x: x["period"])
    if len(inns) != 2:
        raise RuntimeError(f"{c['name']}: {len(inns)} innings - sirf limited-overs match ka recap")
    # har innings ke top batsmen (batting team) aur top bowlers (doosri team)
    for inn in inns:
        bat, bowl = [], []
        for r in d.get("rosters") or []:
            for p in r.get("roster") or []:
                nm = (p.get("athlete") or {}).get("displayName")
                for pl in p.get("linescores") or []:
                    if pl.get("period") != inn["period"]:
                        continue
                    for sub in pl.get("linescores") or [{}]:
                        s = stat_map(sub)
                        if not getattr(cricket_facts, "_shown", False) and s:
                            cricket_facts._shown = True
                            log("stat keys: " + ", ".join(sorted(map(str, s))))
                        if r["team"]["id"] == inn["tid"] and num(s.get("ballsFaced")) > 0:
                            bat.append({"name": nm, "runs": int(num(s.get("runs"))), "balls": int(num(s.get("ballsFaced"))),
                                        "fours": int(num(s.get("fours"))), "sixes": int(num(s.get("sixes"))),
                                        "not_out": str(s.get("outDetails") or s.get("dismissal") or "").lower() in ("", "not out")
                                        and num(s.get("batted")) and not num(s.get("dismissed"))})
                        if r["team"]["id"] != inn["tid"] and num(s.get("overs")) > 0:
                            bowl.append({"name": nm, "wickets": int(num(s.get("wickets"))),
                                         "runs": int(num(s.get("conceded"))), "overs": s.get("overs")})
        bat.sort(key=lambda b: (-b["runs"], b["balls"]))
        bowl.sort(key=lambda b: (-b["wickets"], b["runs"]))
        inn["top_batsmen"] = [{k: v for k, v in b.items() if k != "not_out"} for b in bat[:3]]
        inn["top_bowlers"] = bowl[:2]
    a, b = inns
    if b["winner"]:
        result = f"{b['team']} won by {10 - b['wickets']} wickets"
    elif a["winner"]:
        result = f"{a['team']} won by {a['runs'] - b['runs']} runs"
    else:
        result = "No clear result"
    notes = {n.get("type"): n.get("text") for n in d.get("notes") or []}
    venue = ((d.get("gameInfo") or {}).get("venue") or {})
    return {"sport": "cricket", "match": d["header"].get("name") or c["name"],
            "series": c["lname"], "description": d["header"].get("description"), "toss": notes.get("toss"),
            "venue": venue.get("fullName"), "city": (venue.get("address") or {}).get("city"),
            "innings": [{k: v for k, v in i.items() if k not in ("tid", "period", "winner")} for i in inns],
            "result": result}


# ---------------------------------------------------------------- football
def football_candidates(done):
    out = []
    for lg, w in SOC_LEAGUES.items():
        try:
            sb = get(f"{SOC}/{lg}/scoreboard")
        except Exception:
            continue
        for ev in sb.get("events") or []:
            st = (ev.get("status") or {}).get("type") or {}
            if not st.get("completed") or f"f{ev['id']}" in done or age_h(ev.get("date", "")) > 30:
                continue
            comp = (ev.get("competitions") or [{}])[0]
            names = [(c.get("team") or {}).get("displayName", "").lower() for c in comp.get("competitors") or []]
            goals = sum(int(num(c.get("score"))) for c in comp.get("competitors") or [])
            score = w + 4 * sum(1 for n in names if n in BIG_CLUBS) + min(goals, 6)
            out.append({"sport": "football", "league": lg, "lname": (sb.get("leagues") or [{}])[0].get("name"),
                        "id": ev["id"], "name": ev.get("name"), "score": score})
    return out


def football_facts(c):
    d = get(f"{SOC}/{c['league']}/summary?event={c['id']}")
    comp = d["header"]["competitions"][0]
    teams = []
    for t in comp["competitors"]:
        teams.append({"team": t["team"]["displayName"], "score": int(num(t.get("score"))), "home": t.get("homeAway") == "home"})
    goals, cards = [], []
    for e in d.get("keyEvents") or []:
        typ = ((e.get("type") or {}).get("type") or "")
        who = ", ".join(p["athlete"]["displayName"] for p in e.get("participants") or [] if p.get("athlete"))
        row = {"minute": (e.get("clock") or {}).get("displayValue"), "half": (e.get("period") or {}).get("number"),
               "team": (e.get("team") or {}).get("displayName"), "player": who.split(",")[0] if who else ""}
        if e.get("scoringPlay"):
            row["type"] = "own goal" if "own" in typ else ("penalty" if "penalty" in typ else "goal")
            goals.append(row)
        elif typ == "red-card":
            row["type"] = "red card"
            cards.append(row)
    stats = {}
    for t in (d.get("boxscore") or {}).get("teams") or []:
        s = {x.get("name"): x.get("displayValue") for x in t.get("statistics") or []}
        stats[t["team"]["displayName"]] = {"possession_%": s.get("possessionPct"), "shots": s.get("totalShots"),
                                           "on_target": s.get("shotsOnTarget"), "corners": s.get("wonCorners")}
    h, a = sorted(teams, key=lambda x: not x["home"])
    if h["score"] == a["score"]:
        result = f"{h['team']} {h['score']}-{a['score']} {a['team']} (draw)"
    else:
        w, l = (h, a) if h["score"] > a["score"] else (a, h)
        result = f"{w['team']} beat {l['team']} {w['score']}-{l['score']}"
    venue = ((d.get("gameInfo") or {}).get("venue") or {})
    return {"sport": "football", "match": f"{h['team']} vs {a['team']}", "competition": c["lname"],
            "venue": venue.get("fullName"), "result": result, "score": f"{h['team']} {h['score']} - {a['score']} {a['team']}",
            "goals": goals, "red_cards": cards, "stats": stats}


# ---------------------------------------------------------------- baqi duniya ke khel (ESPN)
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
TEAM_SPORTS = {   # path: (naam, weight, photo hint, fallback footage)
    "basketball/nba": ("basketball", 8, "basketball player", ["basketball game arena", "basketball dunk", "basketball hoop"]),
    "football/nfl": ("american football", 7, "American football player", ["american football game", "american football stadium"]),
    "hockey/nhl": ("ice hockey", 4, "ice hockey player", ["ice hockey game", "ice hockey rink"]),
    "baseball/mlb": ("baseball", 5, "baseball player", ["baseball game stadium", "baseball batter"]),
    "basketball/wnba": ("basketball", 3, "basketball player", ["basketball game arena", "basketball hoop"]),
}
STARS = {"lebron james", "stephen curry", "kevin durant", "giannis antetokounmpo", "luka doncic", "nikola jokic",
         "max verstappen", "lewis hamilton", "lando norris", "charles leclerc", "carlos alcaraz", "jannik sinner",
         "novak djokovic", "aryna sabalenka", "iga swiatek", "coco gauff", "patrick mahomes"}
FALLBACK = {"cricket": ["cricket stadium crowd", "cricket batsman shot", "cricket ball bowler"],
            "football": ["football stadium crowd", "football goal net", "soccer players match"],
            "formula 1": ["formula one race car", "race track cars", "motorsport pit lane"],
            "tennis": ["tennis match court", "tennis player serve", "tennis ball racket"],
            "mma": ["mma fighters training", "boxing gloves ring", "martial arts gym"]}
HINT = {"cricket": "cricketer", "football": "footballer", "formula 1": "racing driver", "tennis": "tennis player",
        "mma": "mixed martial artist"}


def recent(ev):
    return age_h(ev.get("date", "")) <= 30


def team_candidates(done):
    out = []
    for path, (sport, w, _, _) in TEAM_SPORTS.items():
        try:
            sb = get(f"{ESPN}/{path}/scoreboard")
        except Exception:
            continue
        for ev in sb.get("events") or []:
            st = (ev.get("status") or {}).get("type") or {}
            key = f"t{ev['id']}"
            if not st.get("completed") or key in done or not recent(ev):
                continue
            comp = (ev.get("competitions") or [{}])[0]
            pts = sorted(int(num(c.get("score"))) for c in comp.get("competitors") or [])
            close = 3 if len(pts) == 2 and pts[1] - pts[0] <= max(3, pts[1] // 15) else 0
            out.append({"sport": sport, "path": path, "key": key, "id": ev["id"], "name": ev.get("name"),
                        "lname": (sb.get("leagues") or [{}])[0].get("name"), "score": w + close})
    return out


def team_facts(c):
    d = get(f"{ESPN}/{c['path']}/summary?event={c['id']}")
    comp = d["header"]["competitions"][0]
    teams = []
    for t in comp["competitors"]:
        teams.append({"team": t["team"]["displayName"],
                      "score": int(num(t.get("score"))), "home": t.get("homeAway") == "home",
                      "by_period": [x.get("displayValue") for x in t.get("linescores") or []]})
    leaders = []
    for tl in d.get("leaders") or []:
        tn = (tl.get("team") or {}).get("displayName")
        for cat in (tl.get("leaders") or [])[:3]:
            top = (cat.get("leaders") or [{}])[0]
            nm = (top.get("athlete") or {}).get("displayName")
            if nm:
                leaders.append({"team": tn, "stat": cat.get("displayName") or cat.get("name"), "player": nm,
                                "value": top.get("displayValue")})
    h, a = sorted(teams, key=lambda x: not x["home"])
    w, l = (h, a) if h["score"] >= a["score"] else (a, h)
    venue = ((d.get("gameInfo") or {}).get("venue") or {})
    return {"sport": c["sport"], "match": f"{a['team']} at {h['team']}", "competition": c["lname"],
            "venue": venue.get("fullName"), "result": f"{w['team']} beat {l['team']} {w['score']}-{l['score']}",
            "teams": teams, "top_performers": leaders,
            "period_note": "by_period = points in each quarter/period/inning in order"}


def f1_candidates(done):
    out = []
    try:
        sb = get(f"{ESPN}/racing/f1/scoreboard")
    except Exception:
        return out
    for ev in sb.get("events") or []:
        race = next((c for c in ev.get("competitions") or []
                     if ((c.get("type") or {}).get("abbreviation") or "").lower() == "race"), None)
        if not race or not (((race.get("status") or {}).get("type") or {}).get("completed")):
            continue
        key = f"r{race['id']}"
        if key in done or age_h(race.get("date", "")) > 40:
            continue
        out.append({"sport": "formula 1", "key": key, "id": race["id"], "name": ev.get("name"), "lname": "Formula 1",
                    "race": race, "score": 13})
    return out


def f1_facts(c):
    rows = sorted(c["race"].get("competitors") or [], key=lambda x: x.get("order") or 99)
    top = [{"position": r.get("order"), "driver": (r.get("athlete") or {}).get("displayName"),
            "country": ((r.get("athlete") or {}).get("flag") or {}).get("alt")} for r in rows[:10]]
    return {"sport": "formula 1", "match": c["name"], "competition": "Formula 1", "venue": c["name"],
            "result": f"{top[0]['driver']} won the {c['name']}" if top else "", "top_10": top}


def tennis_candidates(done):
    out = []
    for tour in ("atp", "wta"):
        try:
            sb = get(f"{ESPN}/tennis/{tour}/scoreboard")
        except Exception:
            continue
        for ev in sb.get("events") or []:
            for g in ev.get("groupings") or []:
                if "singles" not in (((g.get("grouping") or {}).get("slug")) or "singles"):
                    continue
                for cp in g.get("competitions") or []:
                    if not (((cp.get("status") or {}).get("type") or {}).get("completed")):
                        continue
                    key = f"n{cp['id']}"
                    if key in done or age_h(cp.get("date", "")) > 30 or "singles" not in ((cp.get("type") or {}).get("slug") or ""):
                        continue
                    names = [((x.get("athlete") or {}).get("displayName") or "") for x in cp.get("competitors") or []]
                    rnd = ((cp.get("round") or {}).get("displayName") or "").lower()
                    sc = 5 + 5 * sum(1 for n in names if n.lower() in STARS) + (6 if "final" in rnd else 0)
                    out.append({"sport": "tennis", "key": key, "id": cp["id"], "name": " vs ".join(names),
                                "lname": ev.get("name"), "comp": cp, "round": rnd, "score": sc})
    return out


def tennis_facts(c):
    ps = []
    for x in c["comp"].get("competitors") or []:
        ps.append({"player": (x.get("athlete") or {}).get("displayName"),
                   "country": ((x.get("athlete") or {}).get("flag") or {}).get("alt"),
                   "winner": bool(x.get("winner")),
                   "sets": [int(num(s.get("value"))) for s in x.get("linescores") or []]})
    w = next((p for p in ps if p["winner"]), ps[0])
    l = next((p for p in ps if p is not w), ps[-1])
    score = ", ".join(f"{a}-{b}" for a, b in zip(w["sets"], l["sets"]))
    return {"sport": "tennis", "match": c["name"], "competition": c["lname"], "round": c.get("round"),
            "venue": None, "result": f"{w['player']} beat {l['player']} {score}", "players": ps}


def ufc_candidates(done):
    out = []
    try:
        sb = get(f"{ESPN}/mma/ufc/scoreboard")
    except Exception:
        return out
    for ev in sb.get("events") or []:
        if not ((((ev.get("status") or {}).get("type")) or {}).get("completed")):
            continue
        key = f"u{ev['id']}"
        if key in done or age_h(ev.get("date", "")) > 40:
            continue
        out.append({"sport": "mma", "key": key, "id": ev["id"], "name": ev.get("name"), "lname": "UFC", "ev": ev,
                    "score": 9})
    return out


def ufc_facts(c):
    fights = []
    for cp in c["ev"].get("competitions") or []:
        fs = cp.get("competitors") or []
        w = next((f for f in fs if f.get("winner")), None)
        if not w or len(fs) != 2:
            continue
        l = next(f for f in fs if f is not w)
        fights.append({"weight_class": (cp.get("type") or {}).get("abbreviation"),
                       "winner": (w.get("athlete") or {}).get("displayName"),
                       "loser": (l.get("athlete") or {}).get("displayName"),
                       "winner_record": ((w.get("records") or [{}])[0]).get("summary"),
                       "main_event": bool((cp.get("status") or {}).get("featured")), "date": cp.get("date")})
    fights.sort(key=lambda f: f["date"] or "", reverse=True)
    main = next((f for f in fights if f["main_event"]), fights[0] if fights else None)
    if not main:
        raise RuntimeError("UFC natije nahi")
    return {"sport": "mma", "match": c["name"], "competition": "UFC", "venue": None,
            "result": f"{main['winner']} beat {main['loser']} in the main event",
            "main_event": main, "other_fights": [f for f in fights if f is not main][:4]}


# ---------------------------------------------------------------- script
def write_script(f):
    lang = ("natural spoken Urdu in Urdu script like a PTV/Geo sports anchor (no Hindi words, no Roman); cricket "
            "terms like وکٹ، رنز، اوورز، چوکے، چھکے are fine" if LANG == "ur" else
            "energetic but clear spoken English like a Sky Sports presenter")
    if f["sport"] == "cricket":
        plan = """Scenes in this order (each 25-45 spoken words):
1. intro hook: the result in one exciting line (who beat whom, the margin).
2. toss + FIRST innings: batting team, final score and overs, top batsmen (runs, balls, fours/sixes), best bowlers.
3. SECOND innings: the chase/defence, score, top batsmen, best bowlers, how the match finished.
4. result + one-line wrap-up of the star performers.
5. outro: ask viewers to follow Sports Hubs for every match recap.
"screen" for scenes 2-3 = that innings' score like "PAK 245/7 (50 ov)"; scene 1 and 4 = final result short."""
    elif f["sport"] != "football":
        plan = """Scenes in this order (each 25-45 spoken words):
1. intro hook: the result in one exciting line.
2. how it went: the scores by period / sets / race order / fights exactly as in the data.
3. the star performers with their exact numbers from the data.
4. one more scene with the remaining facts from the data (other results, other top performers).
5. outro: ask viewers to follow Sports Hubs for every sport from around the world.
"screen" = a short score line for that scene, like "LAL 112-108 BOS" or "1. NORRIS" or "SINNER 6-4 7-6"."""
    else:
        plan = """Scenes in this order (each 25-45 spoken words):
1. intro hook: the final score in one exciting line.
2. FIRST half: goals with minute and scorer (or that it was goalless at half time).
3. SECOND half: goals with minute and scorer, red cards, how it finished.
4. match stats (possession, shots) and what the result means only if stated in the data (otherwise just stats).
5. outro: ask viewers to follow Sports Hubs for every match recap.
"screen" = the running score after that part, like "RMA 2-1 BAR (HT)"."""
    prompt = f"""You are the presenter of the Facebook page "Sports Hubs". Write a short vertical match-recap REEL
in {lang} from this REAL match data (JSON):
{json.dumps(f, ensure_ascii=False)}

Rules:
- Use ONLY the facts and numbers in the data. Never invent players, scores, minutes, records, quotes or context.
- Numbers must match the data exactly. Say "according to the scorecard" style naturally, not robotic.
{plan}
- For every scene give "subjects": 0-2 REAL names from the data to show a real photo of (a player who is talked
  about in that scene, the team, or the venue), as their English Wikipedia title.
- "visuals": 1-2 short ENGLISH stock-footage terms of THIS sport ({f["sport"]}) itself (e.g. "cricket batsman shot",
  "basketball dunk arena", "formula one race car", "tennis serve court"). Never logos.
{news.brain_tips("sports")}
Return JSON:
{{"title": "video title, max 10 words, include the team/player names",
  "scenes": [{{"text": "...", "screen": "...", "subjects": ["..."], "visuals": ["..."]}}],
  "caption": "2-3 sentence post description in the same language with the final result",
  "hashtags": ["6 hashtags without #"]}}"""
    j = news.ask_json(prompt)
    if len(j.get("scenes") or []) < 3:
        raise RuntimeError("AI ne script nahi di")
    return j


def build(f, script, used):
    for x in os.listdir(nv.WORK):
        os.remove(os.path.join(nv.WORK, x))
    fb = FALLBACK.get(f["sport"]) or next((v[3] for v in TEAM_SPORTS.values() if v[0] == f["sport"]),
                                          ["sports stadium crowd"])
    date = datetime.datetime.utcnow().strftime("%d %b %Y")
    badge = date if LANG == "ur" else f"MATCH RECAP | {date}"
    scenes = []
    for i, sc in enumerate(script["scenes"][:6]):
        if not str(sc.get("text") or "").strip():
            continue
        subj = [f"@{s}" for s in (sc.get("subjects") or [])[:2] if isinstance(s, str) and s.strip()]
        if i == 0 and f.get("venue"):
            subj = subj[:1] + [f"@{f['venue']}"]
        scenes.append(nv.build_scene(i, "sports", sc["text"], subj + (sc.get("visuals") or []),
                                     (sc.get("screen") or "").strip() or None, badge, used, fb))
    lst = os.path.join(nv.WORK, "all.txt")
    with open(lst, "w") as fh:
        fh.write("".join(f"file '{os.path.abspath(p)}'\n" for p in scenes))
    joined = os.path.join(nv.WORK, "joined.mp4")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    total = nv.duration(joined)
    music = os.path.join(nv.WORK, "music.wav")
    nv.make_music(music, total)
    final = os.path.join(nv.WORK, "match_final.mp4")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", music, "-filter_complex",
            f"[1:a]volume=0.22,afade=t=out:st={max(0, total - 2):.2f}:d=2[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", final])
    log(f"match reel ban gayi {total:.0f}s")
    return final


def description(f, script):
    import seo
    title = (script.get("title") or f["match"]).strip()
    said = " ".join(sc.get("text", "") for sc in script["scenes"])
    src = ("📊 " + ("اسکور کارڈ" if LANG == "ur" else "Scorecard") + ": ESPN / ESPNcricinfo")
    try:
        cap = seo.build(news.ask_json, "sports", title, f"{script.get('caption', '')} {said}", LANG, is_reel=True)
        parts = cap.split("\n\n")
        parts[1:1] = [(script.get("caption") or "").strip(), src]
        parts = [p for p in parts if p]
        parts[-1] += " #reels #matchrecap"
        return "\n\n".join(parts)
    except Exception as e:
        log(f"SEO caption fail ({str(e)[:100]})")
    return f"🏆 {title}\n\n{(script.get('caption') or '').strip()}\n\n{src}\n\n#SportsHubs #reels"


def fact_kind(c):
    if c["sport"] in ("cricket", "football", "formula 1", "tennis", "mma"):
        return c["sport"]
    return "team"


FACTS = {"cricket": cricket_facts, "football": football_facts, "formula 1": f1_facts, "tennis": tennis_facts,
         "mma": ufc_facts, "team": team_facts}


def key_of(c):
    if c.get("key"):
        return c["key"]
    return ("c" if c["sport"] == "cricket" else "f") + str(c["id"])


def main():
    news.CURRENT_PAGE = "sports"
    hist = load_hist()
    done = {m["key"] for m in hist["matches"]}
    cands = []
    for fn in (cricket_candidates, football_candidates, team_candidates, f1_candidates, tennis_candidates,
               ufc_candidates):
        try:
            cands += fn(done)
        except Exception as e:
            log(f"{fn.__name__} fail: {str(e)[:150]}")
    # har dafa alag khel: pichle recaps wala khel peeche (poori duniya ke sports)
    last = [m.get("sport") for m in hist["matches"][-3:]]
    smult = (news.brain().get("sports") or {}).get("match_mult") or {}
    for c in cands:
        c["key"] = key_of(c)
        c["score"] -= 7 * last.count(c["sport"])
        c["score"] += 6 * (float(smult.get(c["sport"], 1)) - 1)     # agent: jis khel ke recap zyada dekhe gaye
    cands.sort(key=lambda c: -c["score"])
    log("Matches: " + " | ".join(f"{c['name']} ({c['score']})" for c in cands[:8]))
    if not cands:
        log("Koi naya khatam shuda bara match nahi - is dafa recap nahi")
        REPORT["posted"]["skip"] = "no match"
        return save(hist)
    err = None
    for c in cands[:4]:
        try:
            f = FACTS[fact_kind(c)](c)
            nv.SUBJECT_HINT = HINT.get(c["sport"]) or next(
                (v[2] for v in TEAM_SPORTS.values() if v[0] == c["sport"]), "")
            log("Facts: " + json.dumps(f, ensure_ascii=False)[:1500])
            script = write_script(f)
            path = build(f, script, hist["used_clips"])
            desc = description(f, script)
            log(f"--- description ---\n{desc}\n")
            meta = {"key": c["key"], "sport": c["sport"], "date": REPORT["time_utc"],
                    "lang": LANG, "match": f["match"], "result": f["result"], "dur": round(nv.duration(path))}
            if not DRY_RUN:
                P = news.PAGES["sports"]
                if not (P["token"] and P["id"]):
                    raise RuntimeError("sports page token/id secret missing")
                meta["post_id"] = nv.post_reel(P, path, desc)
                log(f"posted {meta['post_id']}")
                news.log_post("sports", meta["post_id"], "match", [c["sport"]], f["match"], sport=c["sport"])
            hist["matches"].append(meta)
            REPORT["posted"]["sports"] = meta
            return save(hist)
        except Exception as e:
            err = e
            log(f"{c['name']} ERROR: {e}")
            REPORT["errors"].append(f"{c['name']}: {str(e)[:300]}")
            done.add(c["key"])
    save(hist)
    raise SystemExit(f"recap nahi bana: {err}")


def save(hist):
    hist["matches"] = hist["matches"][-300:]
    hist["used_clips"] = hist["used_clips"][-1500:]
    with open(HIST_FILE, "w", encoding="utf-8") as fh:
        json.dump(hist, fh, ensure_ascii=False, indent=1)
    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, ensure_ascii=False, indent=1, default=str)
    log("Done!")


if __name__ == "__main__":
    main()
