"""
AI employee - content editor (din mein 2 dafa, ai_employee workflow mein).
Har page/channel ki pichhli videos (titles, topics, format) parh kar AI se poochta hai:
  - kya content bar bar ek hi cheez par atka hua hai? -> 'avoid' list
  - page ke mizaj ke mutabiq naye topics/andaaz -> 'try' list
  - kya video har platform (FB / YouTube / TikTok) par gayi?
Natija content_rules.json mein - bots agle idea mein khud follow karte hain. Koi email nahi.
"""
import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ai_agent      # noqa: E402  (brain = Groq/Gemini)

BOTS = {
    "islamic": ("history.json", "Islamic Motivational Videos - FB page, YouTube, TikTok. Authentic Islamic "
                "stories, Quran/hadith lessons, motivation. Respectful, no sectarian topics."),
    "funny": ("funny_history.json", "Hansi Ka Adda - FB, YouTube, TikTok. Clean family-friendly Pakistani Urdu "
              "comedy: funny animal voice-overs, latifay, chat comedy, cartoon stories."),
    "world": ("world_long_history.json", "Atlas Untold - English YouTube country documentaries (real footage)."),
    "world_short": ("world_short_history.json", "Atlas Untold Shorts - English country facts."),
    "frames": ("frames_long_history.json", "Frames of Life - Urdu country documentaries for Pakistani viewers."),
    "frames_short": ("frames_short_history.json", "Frames of Life Shorts - Urdu country facts."),
}


def summary(h):
    keep = ("title", "topic", "theme", "subject", "country", "format", "reel_format", "style", "animal",
            "series_title", "mode", "lang")
    return [{k: x.get(k) for k in keep if x.get(k)} for x in h[-30:]]


def platforms(h):
    last = h[-10:]
    if not last:
        return {}
    has = lambda keys: sum(1 for x in last if any(x.get(k) for k in keys))
    return {"posts": len(last), "facebook": has(("id", "fb_id", "reel_id", "long_id")),
            "youtube": has(("yt_id", "reel_yt", "long_yt", "yt")), "tiktok": has(("tt_id", "tt_long_id"))}


def main():
    rules, report = {}, {}
    for bot, (path, about) in BOTS.items():
        if not os.path.exists(path):
            continue
        try:
            h = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if len(h) < 5:
            continue
        report[bot] = platforms(h)
        try:
            r = ai_agent.brain([
                {"role": "system", "content": "You are the content editor of a social media network. Reply JSON only."},
                {"role": "user", "content": f"""Page: {about}
Its last 30 posts (oldest first): {json.dumps(summary(h), ensure_ascii=False)}
The page's CORE categories and formats (named in the page description above, and the channel's series) are what
its audience follows - NEVER put a whole category, series or format in 'avoid'.
1. 'avoid': only SPECIFIC things repeated too often recently: an exact story/person/incident, a specific joke
   situation, a specific animal or character, a specific country or city, a recurring title wording. Max 8.
2. 'try': 6 fresh SPECIFIC subjects INSIDE the page's core categories and rules (e.g. a story not told yet,
   a country not covered yet, a new everyday joke situation) - same audience, same style, nothing off-brand.
Return {{"avoid": ["..."], "try": ["..."], "note": "one line: is the page repetitive? (Roman Urdu)"}}"""}])
            rules[bot] = {"avoid": [str(x)[:80] for x in (r.get("avoid") or [])][:10],
                          "try": [str(x)[:80] for x in (r.get("try") or [])][:6], "note": str(r.get("note", ""))[:200]}
            print(bot, json.dumps(rules[bot], ensure_ascii=False))
        except Exception as e:
            print(f"{bot}: review fail {e}")
    old = {}
    if os.path.exists("content_rules.json"):
        try:
            old = json.load(open("content_rules.json", encoding="utf-8"))
        except Exception:
            pass
    old.update(rules)
    old["_platforms"] = report
    json.dump(old, open("content_rules.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
