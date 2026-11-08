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
               "usa.1": 5, "uefa.europa": 4, "fifa.world": 10, "fifa.worldq.afc": 4, "fifa.worldq.uefa": 4,
               "fifa.friendly": 3, "eng.fa": 4, "esp.copa_del_rey": 3}
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
            if score <= 0:
                continue
            out.append({"sport": "cricket", "league": lg.get("id"), "lname": lg.get("name"), "id": ev["id"],
                        "name": ev.get("name"), "score": score + (6 if LANG == "ur" else 2)})
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
                        "id": ev["id"], "name": ev.get("name"), "score": score + (5 if LANG == "en" else 0)})
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
- "visuals": 1-2 short ENGLISH stock-footage terms of the sport itself (e.g. "cricket batsman shot",
  "cricket stadium crowd", "football goal net", "football stadium night"). Never logos.

Return JSON:
{{"title": "video title, max 10 words, include both team names",
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
    fb = (["cricket stadium crowd", "cricket batsman shot", "cricket ball bowler"] if f["sport"] == "cricket"
          else ["football stadium crowd", "football goal net", "soccer players match"])
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


def main():
    news.CURRENT_PAGE = "sports"
    hist = load_hist()
    done = {m["key"] for m in hist["matches"]}
    cands = []
    for fn in (cricket_candidates, football_candidates):
        try:
            cands += fn(done)
        except Exception as e:
            log(f"{fn.__name__} fail: {str(e)[:150]}")
    cands.sort(key=lambda c: -c["score"])
    log("Matches: " + " | ".join(f"{c['name']} ({c['score']})" for c in cands[:8]))
    if not cands:
        log("Koi naya khatam shuda bara match nahi - is dafa recap nahi")
        REPORT["posted"]["skip"] = "no match"
        return save(hist)
    err = None
    for c in cands[:4]:
        try:
            f = cricket_facts(c) if c["sport"] == "cricket" else football_facts(c)
            log("Facts: " + json.dumps(f, ensure_ascii=False)[:1500])
            script = write_script(f)
            path = build(f, script, hist["used_clips"])
            desc = description(f, script)
            log(f"--- description ---\n{desc}\n")
            meta = {"key": ("c" if c["sport"] == "cricket" else "f") + str(c["id"]), "date": REPORT["time_utc"],
                    "lang": LANG, "match": f["match"], "result": f["result"], "dur": round(nv.duration(path))}
            if not DRY_RUN:
                P = news.PAGES["sports"]
                if not (P["token"] and P["id"]):
                    raise RuntimeError("sports page token/id secret missing")
                meta["post_id"] = nv.post_reel(P, path, desc)
                log(f"posted {meta['post_id']}")
            hist["matches"].append(meta)
            REPORT["posted"]["sports"] = meta
            return save(hist)
        except Exception as e:
            err = e
            log(f"{c['name']} ERROR: {e}")
            REPORT["errors"].append(f"{c['name']}: {str(e)[:300]}")
            done.add(("c" if c["sport"] == "cricket" else "f") + str(c["id"]))
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
