"""
Web Builder page ka AGENT (dimagh) - roz 2 dafa chalta hai (brain.yml).
Facebook se har pic / reel / video ke views + reactions + comments + shares khud parhta hai, phir dekhta hai:
  - kaun sa product (POS / website / app / store / social / autopilot) zyada chala   -> focus_mult
  - kis business wali video (restaurant, pharmacy ...) zyada dekhi gayi             -> spot_mult
  - kis rang ke khandan wale posts zyada chale                                      -> color_mult
  - kaun si zubaan, kaun sa type (pic / reel / long)                                -> report
AI (Gemini, na chale to Groq) ko asli data dikha kar writer ke liye sabaq (tips) likhwata hai.
Sab webbuilder_brain.json mein - webbuilder.py, wb_video.py aur wb_theme.py agle post mein khud lagate hain.
Kuch band kabhi nahi hota (0.4x tak kam), taake har cheez phir bhi aati rahe aur rang har dafa naya rahe.
"""
import datetime
import json
import os
import time

import brain
import wb_theme

PICS = "webbuilder_history.json"
VIDS = "webbuilder_video_history.json"
OUT = "webbuilder_brain.json"
REPORT_FILE = "webbuilder_brain_report.json"
MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3-flash-preview", "gemini-2.5-flash",
          "gemini-2.5-flash-lite"]


def load(f):
    try:
        return json.load(open(f, encoding="utf-8"))
    except Exception:
        return {} if f == PICS else []


def ask_json(prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=key)
            for m in MODELS:
                try:
                    res = client.models.generate_content(
                        model=m, contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4))
                    return json.loads(res.text)
                except Exception as e:
                    print(f"{m}: {str(e)[:120]}")
                    time.sleep(3)
        except Exception as e:
            print(f"Gemini: {str(e)[:120]}")
    import groq_backup
    if groq_backup.enabled():
        return groq_backup.ask_json(prompt, 0.4, print)
    return {}


def main():
    tok = os.environ.get("WB_PAGE_TOKEN")
    if not tok:
        raise SystemExit("WB_PAGE_TOKEN missing")
    now = datetime.datetime.utcnow()
    rows = [{**p, "kind": "pic"} for p in (load(PICS).get("posts") or [])] + \
        [{**v, "focus": v.get("focus") or "all"} for v in load(VIDS)]
    R = []
    for h in rows:
        pid = h.get("post_id")
        if not pid or pid == "dry_run":
            continue
        try:
            d = datetime.datetime.strptime(h["date"], "%Y-%m-%d %H:%M")
        except Exception:
            continue
        age = (now - d).total_seconds() / 3600
        if age < brain.MIN_AGE_H or age > 21 * 24:
            continue
        m = brain.metrics({"id": pid, "fmt": "pic" if h["kind"] == "pic" else "reel"}, tok)
        if m["err"] and not m["score"]:
            print(f"{pid}: {m['err']}")
        if h.get("hue") is not None:
            h["color"] = wb_theme.family(h["hue"])
        R.append({**h, **m, "hour": d.hour})
        time.sleep(0.3)
    print(f"{len(R)} posts ka data mila")
    old = load(OUT) if os.path.exists(OUT) else {}
    old = old if isinstance(old, dict) else {}
    rep = {"time_utc": now.strftime("%Y-%m-%d %H:%M"), "posts": len(R),
           "views": sum(r["views"] for r in R), "engagement": sum(r["eng"] for r in R)}
    if len(R) < 6:
        rep["note"] = "Abhi data kam hai - purana plan jari"
        json.dump(rep, open(REPORT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(rep)
        return
    if not rep["views"]:
        brain.K_SHRINK = 8
    base = {}
    for r in R:                     # har type (pic / reel / long) apne hi average se naapa jaye
        base.setdefault(r["kind"], []).append(r["score"])
    for r in R:
        b = base[r["kind"]]
        avg = sum(b) / len(b)
        r["ratio"] = r["score"] / avg if avg else 1

    def by(field, only=None):
        g = {}
        for r in R:
            if only and not only(r):
                continue
            k = r.get(field)
            if k is not None and k != "":
                g.setdefault(str(k), []).append(r["ratio"])
        return {k: (round(brain.gmean(v), 2), len(v)) for k, v in g.items()}

    def mult(stats):
        return {k: brain.clamp(brain.shrink(max(x, 0.05), n)) for k, (x, n) in stats.items()}

    fo = by("focus", lambda r: r["kind"] == "pic")
    sp = by("spotlight", lambda r: r["kind"] != "pic")
    co, la, ki, hr = by("color"), by("lang"), by("kind"), by("hour")
    top = sorted(R, key=lambda r: -r["ratio"])[:6]
    low = sorted(R, key=lambda r: r["ratio"])[:6]
    line = lambda r: (f"[{r['kind']}/{r.get('lang')}] {r.get('title') or r.get('focus')} "
                      f"(business {r.get('spotlight', '-')}, views {r['views']}, eng {r['eng']}, x{r['ratio']:.2f})")
    ai = ask_json(f"""You are the marketing head of the Facebook page "Web Builder" that sells websites, mobile apps,
POS software (mainly Saudi Arabia, UAE, Pakistan) and "AutoPilot AI" (automatic social media) to businesses.
Posts are pics, reels and long promo videos in English, Urdu/Hindi and Arabic. Goal: more views, comments and
WhatsApp messages from business owners -> sales. Prices are never mentioned in posts.
REAL performance of the last 3 weeks (x = score vs page average of the same type):

BEST:
{chr(10).join(line(r) for r in top)}

WORST:
{chr(10).join(line(r) for r in low)}

By product (pics): {json.dumps(fo, ensure_ascii=False)}
By business shown (videos): {json.dumps(sp, ensure_ascii=False)}
By language: {json.dumps(la, ensure_ascii=False)}
By type: {json.dumps(ki, ensure_ascii=False)}

Return JSON:
{{"tips": ["4-6 short, concrete instructions for the promo video script writer: which hooks, benefits, business
           types, title styles and calls to action to use more or avoid - based only on this data; never prices"],
  "summary": "3 sentences in simple Roman Urdu for the page owner: kya chal raha hai, kya nahi, agent ne kya badla"}}""")
    plan = {"updated": rep["time_utc"], "focus_mult": mult(fo), "spot_mult": mult(sp), "color_mult": mult(co),
            "tips": [str(x)[:220] for x in ((ai or {}).get("tips") or old.get("tips") or [])][:6]}
    json.dump(plan, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep.update({"by_focus": fo, "by_business": sp, "by_color": co, "by_lang": la, "by_kind": ki, "by_hour": hr,
                "best": [line(r) for r in top[:3]], "summary": (ai or {}).get("summary", ""), "plan": plan})
    json.dump(rep, open(REPORT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
