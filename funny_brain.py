"""
Hansi Ka Adda ka AGENT (dimagh) - roz chalta hai (brain.yml).
Facebook se har reel/video ke views + reactions parhta hai, dekhta hai kaun sa format
(people / chat / cartoon), kaun sa reel andaaz (pov, latifay, types...), kaun sa comedy style aur topic
zyada hansa raha hai - aur funny_brain.json mein plan khud badalta hai:
  format_mult / reel_format_mult / style_mult : jo chala wo zyada, jo nahi chala wo kam (0.4x tak, band kabhi nahi)
  tips : AI writer ko sabaq - har nayi script (reel, chat, cartoon, lambi video) mein lagte hain
"""
import datetime
import json
import os
import time

import brain
import news

HIST = "funny_history.json"
OUT = "funny_brain.json"
REPORT_FILE = "funny_brain_report.json"


def main():
    tok = os.environ.get("FUNNY_PAGE_TOKEN")
    if not tok:
        raise SystemExit("FUNNY_PAGE_TOKEN missing")
    now = datetime.datetime.utcnow()
    try:
        H = json.load(open(HIST, encoding="utf-8"))
    except Exception:
        H = []
    R = []
    for h in H:
        if not h.get("id"):
            continue
        try:
            d = datetime.datetime.strptime(h["date"], "%Y-%m-%d %H:%M")
        except Exception:
            continue
        age = (now - d).total_seconds() / 3600
        if age < brain.MIN_AGE_H or age > 21 * 24:
            continue
        m = brain.metrics({"id": h["id"], "fmt": h.get("mode", "reel")}, tok)
        if m["err"] and not m["score"]:
            print(f"{h['id']}: {m['err']}")
        R.append({**h, **m, "hour": d.hour})
        time.sleep(0.3)
    print(f"{len(R)} videos ka data mila")
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        old = {}
    rep = {"time_utc": now.strftime("%Y-%m-%d %H:%M"), "videos": len(R),
           "views": sum(r["views"] for r in R), "engagement": sum(r["eng"] for r in R)}
    if len(R) < 6:
        rep["note"] = "Abhi data kam hai - purana plan jari"
        json.dump(rep, open(REPORT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(rep)
        return
    base = {}
    for r in R:
        base.setdefault(r.get("mode", "reel"), []).append(r["score"])
    for r in R:
        b = base[r.get("mode", "reel")]
        avg = sum(b) / len(b)
        r["ratio"] = r["score"] / avg if avg else 1

    def by(field):
        g = {}
        for r in R:
            k = r.get(field)
            if k:
                g.setdefault(str(k), []).append(r["ratio"])
        return {k: (round(brain.gmean(v), 2), len(v)) for k, v in g.items()}

    def mult(stats):
        return {k: brain.clamp(brain.shrink(max(x, 0.05), n)) for k, (x, n) in stats.items()}

    fm, rf, st, tp, hr = by("format"), by("reel_format"), by("style"), by("topic"), by("hour")
    top = sorted(R, key=lambda r: -r["ratio"])[:6]
    low = sorted(R, key=lambda r: r["ratio"])[:6]
    line = lambda r: (f"[{r.get('mode')}/{r.get('format')}/{r.get('reel_format') or '-'}] {r.get('title')} "
                      f"(topic {r.get('topic')}, views {r['views']}, eng {r['eng']}, x{r['ratio']:.2f})")
    news.CURRENT_PAGE = "funny"
    ai = {}
    try:
        ai = news.ask_json(f"""You are the head of comedy at the Pakistani Facebook comedy page "Hansi Ka Adda"
(Urdu comedy reels and videos about everyday desi life; goal: people laugh, share, tag friends, follow ->
monetization income). REAL performance of the last 3 weeks (x = score vs page average of the same type):

FUNNIEST / BEST:
{chr(10).join(line(r) for r in top)}

WORST:
{chr(10).join(line(r) for r in low)}

By format: {json.dumps(fm, ensure_ascii=False)}
By reel structure: {json.dumps(rf, ensure_ascii=False)}
By topic: {json.dumps(tp, ensure_ascii=False)}

Find what makes people laugh and share on THIS page. Return JSON:
{{"tips": ["4-6 short, concrete instructions for the comedy script writer: which situations, characters, joke
           structures, hooks and title styles to use more or avoid - based only on this data; clean family humor"],
  "summary": "3 sentences in simple Roman Urdu for the page owner: kya chal raha hai, kya nahi, kya badla"}}""")
    except Exception as e:
        print(f"AI fail: {str(e)[:150]}")
    plan = {"updated": rep["time_utc"], "format_mult": mult(fm), "reel_format_mult": mult(rf),
            "style_mult": mult(st), "topic_mult": mult(tp),
            "tips": [str(x)[:220] for x in (ai.get("tips") or old.get("tips") or [])][:6]}
    json.dump(plan, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep.update({"by_format": fm, "by_reel_format": rf, "by_topic": tp, "by_hour": hr,
                "best": [line(r) for r in top[:3]], "summary": ai.get("summary", ""), "plan": plan})
    json.dump(rep, open(REPORT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
