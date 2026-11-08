"""
News Act + Sports Hubs ka AGENT (dimagh) - roz chalta hai.

1. Facebook se har post ke views / reactions / comments / shares khud parhta hai (free Graph API).
2. Hisab lagata hai: kaun sa topic, kaun sa khel, kaun si zubaan, kaun sa waqt aur format zyada views laya.
3. Gemini (free key) ko data dikhata hai - wo sabaq (tips) likhta hai ke kaisi khabar / hook chalta hai.
4. Apna plan khud badalta hai (news_brain.json):
   - topic_mult  : jo topic zyada chala wo zyada, jo kam chala wo kam (khatam kabhi nahi - 0.4x tak)
   - match_mult  : kis khel ke recap zyada dekhe gaye
   - lang_flip   : jis zubaan ke views zyada, kuch slots us zubaan mein badal jate hain (max 40%)
   - tips        : writer AI ko hidayat - har nayi post/reel/recap mein lagti hain
5. brain_report.json mein Roman Urdu report.
"""
import datetime
import json
import math
import os
import time

import requests

import news

LOG_FILE = news.POSTS_LOG
OUT = news.BRAIN_FILE
REPORT_FILE = "brain_report.json"
G = f"https://graph.facebook.com/{news.GRAPH_VER}"
MIN_AGE_H = 6          # itni der baad views kaafi had tak pakke ho jate hain
DAYS = 21
K_SHRINK = 0          # 0 = normal; views na milen to 8
VIEW_KEYS = ("blue_reels_play_count", "fb_reels_total_plays", "total_video_views", "post_video_views",
             "post_media_view", "post_impressions_unique", "post_impressions")


def log(m):
    print(m, flush=True)


def get(url, **p):
    try:
        r = requests.get(url, params=p, timeout=40)
        return r.json()
    except Exception as e:
        return {"error": {"message": str(e)}}


def _val(d):
    v = (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value") if isinstance(
        d.get("total_value"), dict) else 0)
    if isinstance(v, dict):
        v = sum(x for x in v.values() if isinstance(x, (int, float)))
    return v if isinstance(v, (int, float)) else 0


def metrics(p, token):
    """Ek post ke views + engagement."""
    pid, views, eng, err = p["id"], 0, 0, ""
    if p["fmt"] in ("pic", "breaking"):
        j = get(f"{G}/{pid}", access_token=token,
                fields="reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0),shares")
        if "error" in j:
            err = j["error"].get("message", "")[:120]
        eng = ((j.get("reactions") or {}).get("summary") or {}).get("total_count", 0) + \
            2 * ((j.get("comments") or {}).get("summary") or {}).get("total_count", 0) + \
            3 * (j.get("shares") or {}).get("count", 0)
        for m in ("post_media_view", "post_impressions_unique", "post_impressions"):
            k = get(f"{G}/{pid}/insights", access_token=token, metric=m)
            if k.get("data"):
                views = _val(k["data"][0])
                if views:
                    break
    else:
        k = get(f"{G}/{pid}/video_insights", access_token=token)
        vals = {d.get("name"): _val(d) for d in k.get("data") or []}
        views = max([vals.get(x, 0) for x in VIEW_KEYS] + [0])
        if "error" in k:
            err = k["error"].get("message", "")[:120]
        j = get(f"{G}/{pid}", access_token=token,
                fields="likes.summary(true).limit(0),comments.summary(true).limit(0)")
        v = get(f"{G}/{pid}", access_token=token, fields="views")     # bina read_insights ke bhi milta hai
        if isinstance(v.get("views"), int):
            views = max(views, v["views"])
        eng = ((j.get("likes") or {}).get("summary") or {}).get("total_count", 0) + \
            2 * ((j.get("comments") or {}).get("summary") or {}).get("total_count", 0)
        eng = max(eng, vals.get("post_video_social_actions", 0) or 0)
    score = views + 25 * eng if views else 25 * eng
    return {"views": views, "eng": eng, "score": score, "err": err}


def gmean(xs):
    return math.exp(sum(math.log(x + 0.05) for x in xs) / len(xs)) if xs else 1.0


def shrink(r, n, k=3):
    """k bara = kam yaqeen (sirf likes ho, views na hon to data shor wala hota hai)."""
    k = K_SHRINK if K_SHRINK else k
    """Kam data par zyada yaqeen nahi - 1 ki taraf kheencho."""
    return math.exp(math.log(r) * n / (n + k))


def clamp(x, lo=0.4, hi=2.5):
    return round(max(lo, min(hi, x)), 2)


def load_log():
    try:
        with open(LOG_FILE, encoding="utf-8") as f:
            L = json.load(f)
    except Exception:
        L = []
    have = {p["id"] for p in L}
    # purani pic posts (log banne se pehle wali) bhi shamil
    try:
        h = news.load_history()
        for page in ("news", "sports"):
            for p in h[page]:
                if p.get("post_id") and p["post_id"] not in have:
                    L.append({"date": p["date"], "page": page, "id": p["post_id"],
                              "fmt": "breaking" if p.get("breaking") else "pic", "lang": p.get("lang", "en"),
                              "topics": [p.get("topic")], "sport": None, "title": p.get("title", "")})
    except Exception as e:
        log(f"history backfill skip: {e}")
    return L


def main():
    now = datetime.datetime.utcnow()
    L = load_log()
    rows = []
    for p in L:
        try:
            d = datetime.datetime.strptime(p["date"], "%Y-%m-%d %H:%M")
        except Exception:
            continue
        age = (now - d).total_seconds() / 3600
        if age < MIN_AGE_H or age > DAYS * 24:
            continue
        tok = news.PAGES.get(p["page"], {}).get("token")
        if not tok:
            continue
        m = metrics(p, tok)
        if m["err"] and not m["score"]:
            log(f"{p['id']}: {m['err']}")
        rows.append({**p, **m, "hour": d.hour})
        time.sleep(0.3)
    log(f"{len(rows)} posts ka data mila")

    old = news.brain()
    plan = {"updated": now.strftime("%Y-%m-%d %H:%M"), "posts_checked": len(rows)}
    report = {"time_utc": plan["updated"], "posts_checked": len(rows), "pages": {}}
    lang_logs = []
    for page in ("news", "sports"):
        R = [r for r in rows if r["page"] == page]
        prev = old.get(page) or {}
        P = {"topic_mult": prev.get("topic_mult", {}), "match_mult": prev.get("match_mult", {}),
             "tips": prev.get("tips", [])}
        rep = {"posts": len(R), "views": sum(r["views"] for r in R), "engagement": sum(r["eng"] for r in R)}
        if len(R) < 6:
            rep["note"] = "Abhi data kam hai - kam az kam 6 posts ke views chahiye, purana plan jari"
            plan[page], report["pages"][page] = P, rep
            continue
        brain_k = 8 if not rep["views"] else 0
        globals()["K_SHRINK"] = brain_k
        # har format ka apna average (reel ka pic se muqabla nahi)
        base = {}
        for r in R:
            base.setdefault(r["fmt"], []).append(r["score"])
        for r in R:
            avg = sum(base[r["fmt"]]) / len(base[r["fmt"]]) or 1
            r["ratio"] = r["score"] / avg if avg else 1

        def by(keyf):
            g = {}
            for r in R:
                for k in keyf(r):
                    if k:
                        g.setdefault(k, []).append(r["ratio"])
            return {k: (round(gmean(v), 2), len(v)) for k, v in g.items()}

        topics = by(lambda r: r.get("topics") or [])
        tm = {t: clamp(shrink(max(r, 0.05), n)) for t, (r, n) in topics.items()}
        sports = by(lambda r: [r["sport"]] if r["fmt"] == "match" else [])
        mm = {t: clamp(shrink(max(r, 0.05), n)) for t, (r, n) in sports.items()}
        langs = by(lambda r: [r["lang"]])
        hours = by(lambda r: [f"{r['hour']:02d}:00 UTC"])
        fmts = {f: (round(sum(v) / len(v)), len(v)) for f, v in base.items()}
        if "en" in langs and "ur" in langs and langs["en"][1] >= 4 and langs["ur"][1] >= 4:
            lang_logs.append(math.log(langs["en"][0] + 0.05) - math.log(langs["ur"][0] + 0.05))

        top = sorted(R, key=lambda r: -r["ratio"])[:6]
        low = sorted(R, key=lambda r: r["ratio"])[:6]
        fmtline = lambda r: f"[{r['fmt']}/{r['lang']}/{','.join(t for t in r['topics'] if t)}] {r['title']} " \
                            f"(views {r['views']}, eng {r['eng']}, x{r['ratio']:.2f})"
        news.CURRENT_PAGE = page
        ai = {}
        try:
            ai = news.ask_json(f"""You are the growth strategist of the Facebook page "{news.PAGES[page]['name']}"
({'world news' if page == 'news' else 'world sports'}; posts in English and Urdu; goal: more views, followers and
monetization income). Here is REAL performance data from the last {DAYS} days (x = score vs average of same format):

BEST posts:
{chr(10).join(fmtline(r) for r in top)}

WORST posts:
{chr(10).join(fmtline(r) for r in low)}

By topic (x, count): {json.dumps(topics)}
By language: {json.dumps(langs)}
By posting hour: {json.dumps(hours)}
By format (avg score, count): {json.dumps(fmts)}

Find the patterns. Return JSON:
{{"tips": ["4-6 short, concrete instructions for the AI writer about which stories, angles, hooks and headline
            styles to prefer or avoid on THIS page, based only on the data (must stay truthful, no clickbait lies)"],
  "topic_adjust": {{"topic_name": 0.5-2.0 multiplier, only for topics you have a clear reason to change}},
  "summary": "3-4 sentences in simple Roman Urdu for the page owner: what works, what doesn't, what you changed"}}""")
        except Exception as e:
            log(f"{page} AI fail: {str(e)[:150]}")
        for t, v in (ai.get("topic_adjust") or {}).items():
            try:
                tm[t] = clamp(math.sqrt(tm.get(t, 1) * float(v)))     # data + AI ka darmiyana faisla
            except Exception:
                pass
        P["topic_mult"] = tm
        P["match_mult"] = mm or P["match_mult"]
        if ai.get("tips"):
            P["tips"] = [str(x)[:220] for x in ai["tips"]][:6]
        plan[page] = P
        rep.update({"by_topic": topics, "by_language": langs, "by_hour": hours, "by_format": fmts,
                    "topic_mult": tm, "match_mult": mm, "tips": P["tips"],
                    "best": [fmtline(r) for r in top[:3]], "summary": ai.get("summary", "")})
        report["pages"][page] = rep

    # zubaan: jo zyada chali us taraf kuch slots (max 40%), dusri kabhi band nahi
    flip = old.get("lang_flip") or {"ur_to_en": 0, "en_to_ur": 0}
    if lang_logs:
        d = sum(lang_logs) / len(lang_logs)
        p = round(min(0.4, abs(d) * 0.3), 2)
        flip = {"ur_to_en": p if d > 0 else 0, "en_to_ur": p if d < 0 else 0}
    plan["lang_flip"] = flip
    report["lang_flip"] = flip

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    log(json.dumps(report, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
