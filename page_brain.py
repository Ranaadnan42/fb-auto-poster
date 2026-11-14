"""
Islamic Motivational Videos + Frames of Life ka AGENT (dimagh) - roz 2 dafa (brain.yml).
Pehle ye dono sirf bot the (fixed baari se topic). Ab agent:
  1. Facebook se har reel / video ke ASLI views + likes + comments khud parhta hai
  2. dekhta hai kaun sa theme (Islamic) / kaun si series (Frames) zyada chali
  3. plan khud badalta hai: *_mult (jo chala wo zyada, jo nahi chala kam - 0.4x tak, band kabhi nahi)
  4. AI (Gemini, na chale to Groq) asli data dekh kar writer ke liye sabaq (tips) likhta hai
main.py / world.py agli video mein ye plan khud lagate hain.
"""
import datetime
import json
import os
import time

import brain

CFG = {
    "islamic": {"token": "FB_PAGE_TOKEN", "files": ["history.json"], "group": "theme",
                "ids": [("reel_id", "reel"), ("long_id", "long")], "out": "islamic_brain.json",
                "who": 'the Facebook page "Islamic Motivational Videos" (Urdu Islamic stories, reminders, hadith; '
                       "audience: Muslims in the Gulf, UK, USA, Canada, Europe and Pakistan)"},
    "frames": {"token": "FRAMES_PAGE_TOKEN", "files": ["frames_long_history.json", "frames_short_history.json"],
               "group": "series", "ids": [("fb_id", None)], "out": "frames_brain.json",
               "who": 'the Facebook page "Frames of Life" (Urdu videos for Pakistanis about living, jobs, visas, '
                      "cost of living and travel abroad - Gulf, UK, Europe, Canada, USA, Australia)"},
}
MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


def ask_json(prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=key)
            for m in MODELS:
                try:
                    res = client.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.4))
                    return json.loads(res.text)
                except Exception as e:
                    print(f"{m}: {str(e)[:120]}")
                    time.sleep(3)
        except Exception as e:
            print(f"Gemini: {str(e)[:120]}")
    try:
        import groq_backup
        if groq_backup.enabled():
            return groq_backup.ask_json(prompt, 0.4, print)
    except Exception as e:
        print(f"Groq: {str(e)[:120]}")
    return {}


def think(page):
    c = CFG[page]
    tok = os.environ.get(c["token"])
    if not tok:
        print(f"{page}: {c['token']} missing - skip")
        return
    now = datetime.datetime.utcnow()
    R = []
    for f in c["files"]:
        try:
            rows = json.load(open(f, encoding="utf-8"))
        except Exception:
            rows = []
        kind_default = "short" if "short" in f else "long"
        for h in rows:
            try:
                d = datetime.datetime.strptime(h["date"], "%Y-%m-%d %H:%M")
            except Exception:
                continue
            age = (now - d).total_seconds() / 3600
            if age < brain.MIN_AGE_H or age > 21 * 24:
                continue
            for key, kind in c["ids"]:
                pid = h.get(key)
                if not pid or pid == "dry_run":
                    continue
                m = brain.metrics({"id": pid, "fmt": "reel"}, tok)
                if m["err"] and not m["score"]:
                    print(f"{pid}: {m['err']}")
                R.append({**h, **m, "kind": kind or kind_default, "hour": d.hour})
                time.sleep(0.3)
    print(f"{page}: {len(R)} videos ka data")
    try:
        old = json.load(open(c["out"], encoding="utf-8"))
    except Exception:
        old = {}
    rep = {"time_utc": now.strftime("%Y-%m-%d %H:%M"), "videos": len(R),
           "views": sum(r["views"] for r in R), "engagement": sum(r["eng"] for r in R)}
    if len(R) < 6:
        rep["note"] = "Abhi data kam hai - purana plan jari"
        json.dump(rep, open(c["out"].replace(".json", "_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    brain.K_SHRINK = 0 if rep["views"] else 8
    base = {}
    for r in R:
        base.setdefault(r["kind"], []).append(r["score"])
    for r in R:
        b = base[r["kind"]]
        r["ratio"] = r["score"] / (sum(b) / len(b)) if sum(b) else 1

    def by(field):
        g = {}
        for r in R:
            k = r.get(field)
            if k:
                g.setdefault(str(k), []).append(r["ratio"])
        return {k: (round(brain.gmean(v), 2), len(v)) for k, v in g.items()}

    grp, la, ki = by(c["group"]), by("lang"), by("kind")
    mult = {k: brain.clamp(brain.shrink(max(x, 0.05), n)) for k, (x, n) in grp.items()}
    top = sorted(R, key=lambda r: -r["ratio"])[:6]
    low = sorted(R, key=lambda r: r["ratio"])[:6]
    line = lambda r: (f"[{r['kind']}/{r.get('lang', 'ur')}] {r.get('title')} ({c['group']} {r.get(c['group'])}, "
                      f"views {r['views']}, eng {r['eng']}, x{r['ratio']:.2f})")
    ai = ask_json(f"""You are the content head of {c['who']}. Goal: more views, shares and followers from
high-income countries and the Gulf -> monetization income. REAL performance of the last 3 weeks
(x = score vs page average of the same type):

BEST:
{chr(10).join(line(r) for r in top)}

WORST:
{chr(10).join(line(r) for r in low)}

By {c['group']}: {json.dumps(grp, ensure_ascii=False)}
By type: {json.dumps(ki, ensure_ascii=False)}

Return JSON:
{{"tips": ["4-6 short, concrete instructions for the script writer: which topics, story types, hooks, title
           styles and lengths to use more or avoid - based only on this data"],
  "summary": "3 sentences in simple Roman Urdu for the page owner: kya chal raha hai, kya nahi, agent ne kya badla"}}""")
    plan = {"updated": rep["time_utc"], "mult": mult,
            "tips": [str(x)[:220] for x in ((ai or {}).get("tips") or old.get("tips") or [])][:6]}
    json.dump(plan, open(c["out"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep.update({"by_" + c["group"]: grp, "by_lang": la, "by_kind": ki, "best": [line(r) for r in top[:3]],
                "summary": (ai or {}).get("summary", ""), "plan": plan})
    json.dump(rep, open(c["out"].replace(".json", "_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:3000])


def load(page):
    """main.py / world.py ke liye: (mult, tips_text)."""
    try:
        p = json.load(open(CFG[page]["out"], encoding="utf-8"))
    except Exception:
        return {}, ""
    tips = [str(t) for t in (p.get("tips") or [])][:6]
    txt = ("\nLessons from this page's REAL results (agent - follow them):\n- " + "\n- ".join(tips) + "\n") if tips else ""
    return p.get("mult") or {}, txt


if __name__ == "__main__":
    for pg in CFG:
        try:
            think(pg)
        except Exception as e:
            print(f"{pg} agent fail: {str(e)[:200]}")
