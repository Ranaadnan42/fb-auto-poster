"""
Trend scout - har page ka agent roz khud dekhta hai log AAJ KAL kya dekh rahe hain (reels AUR lambi videos dono),
phir us hisaab se apna topic chunta hai.
  1) YouTube: pichhle 7 din mein is niche ki sab se zyada dekhi gayi videos (shorts + lambi) asal views ke saath
  2) Gemini + Google Search: is hafte Facebook/Instagram/TikTok/YouTube par is niche mein kya viral hai
Din mein ek dafa banta hai (trends/<page>.json mein cache), har prompt mein content_rules.text() ke zariye jata hai.
Kuch na mile to khali string - koi agent nahi rukta.
"""
import datetime
import json
import os
import random
import re

import requests

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trends")

NICHES = {
    "islamic": ("Islamic motivational videos in Urdu/Hindi (Quran, Hadith, prophets' stories, duas, Islamic history, reminders)",
                ["islamic bayan urdu", "islamic motivational", "prophet story urdu", "islamic short video",
                 "dua urdu", "quran tilawat beautiful", "islamic history urdu", "naat 2026"]),
    "funny": ("Pakistani/Indian Urdu-Hindi comedy videos (funny animal voiceovers, cartoon comedy, desi family jokes, chat comedy)",
              ["funny video urdu", "pakistani comedy", "funny animals urdu", "desi funny", "cartoon comedy urdu",
               "funny shorts pakistan", "hindi comedy video", "funny dubbing"]),
    "frames": ("Urdu travel & world documentaries (countries, cities, cultures, food, strange facts about places)",
               ["urdu documentary", "country documentary urdu", "travel documentary hindi", "amazing facts countries",
                "world documentary", "strange places on earth", "country facts", "travel vlog"]),
    "world": ("English travel & world documentaries (countries, cities, cultures, food, strange facts about places)",
              ["country documentary", "travel documentary", "amazing facts countries", "strange places on earth",
               "world documentary 2026", "most beautiful countries", "life in country", "country explained"]),
    "news": ("Pakistan & world news explainers in Urdu", ["urdu news", "pakistan news today", "world news urdu",
                                                         "breaking news explained", "news analysis urdu"]),
    "sports": ("cricket & football news and highlights in Urdu", ["cricket news urdu", "pakistan cricket",
                                                                  "football highlights", "cricket highlights", "sports news"]),
    "war": ("war history documentaries (ancient battles, World War I and II, famous wars - why they started, who won)",
            ["war history documentary", "world war 2 documentary", "history of war", "ancient battles",
             "military history", "battle explained", "ww2 footage", "history documentary"]),
    "wild": ("wildlife documentaries - real animals of every country (predators, rare animals, animal facts)",
             ["wildlife documentary", "animals of africa", "amazing animals", "wild animals 4k", "animal facts",
              "predators documentary", "rare animals", "nature documentary animals"]),
    "birds": ("bird documentaries - colorful birds of the world, bird songs, courtship dances, birdwatching",
              ["colorful birds", "beautiful birds 4k", "bird sounds", "birds of paradise dance", "parrots",
               "hummingbird slow motion", "birdwatching", "rare birds"]),
    "pets": ("cute and funny dogs and cats, puppies, kittens, dog and cat breeds",
             ["funny dogs", "funny cats", "cute puppies", "cute kittens", "dog breeds", "cat breeds",
              "golden retriever", "husky"]),
    "faizi": ("trending ladies dress designs and women's fashion (party wear, wedding & bridal, Eid/festive, formal, "
              "lawn/summer, maxi, gown, anarkali, sharara, lehenga, kaftan, abaya, co-ord sets) - which exact styles, "
              "cuts, colors, fabrics and embroidery are trending right now",
              ["new dress design", "trending dress design", "party wear dress", "bridal dress", "maxi dress design",
               "sharara design", "anarkali dress", "abaya design", "fashion trends women"]),
    "scenic": ("beautiful nature and scenic travel places", ["nature 4k", "beautiful places", "relaxing nature",
                                                            "travel shorts", "drone footage nature", "hidden places on earth"]),
}


def _niche(bot):
    b = (bot or "").replace("_short", "")
    return b, NICHES.get(b)


def _yt_token():
    try:
        import yt_tokens
    except Exception:
        yt_tokens = None
    for p, acct in (("YT_FRAMES_", "frames"), ("YT_WORLD_", "world"), ("YT_ISLAMIC_", "islamic"),
                    ("YT_FUNNY_", "funny"), ("YT_", "legends")):
        cid, sec, ref = (os.environ.get(p + k) for k in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN"))
        if not (cid and sec):
            continue
        try:
            ref = (yt_tokens.get(acct, sec) if yt_tokens else None) or ref
            j = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
                "client_id": cid, "client_secret": sec, "refresh_token": ref, "grant_type": "refresh_token"}).json()
            if j.get("access_token"):
                return j["access_token"]
        except Exception:
            pass
    return None


def youtube_top(queries, n=6):
    """Pichhle 7 din ki sab se zyada dekhi gayi videos - shorts aur lambi dono, duration ke saath."""
    tok = _yt_token()
    if not tok:
        return []
    H = {"Authorization": f"Bearer {tok}"}
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = []
    for q in random.sample(queries, min(n, len(queries))):
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/search", headers=H, timeout=40, params={
                "part": "id", "q": q, "type": "video", "order": "viewCount", "publishedAfter": since,
                "maxResults": 10}).json()
            ids += [i["id"]["videoId"] for i in r.get("items", []) if i.get("id", {}).get("videoId")]
        except Exception:
            pass
    out = []
    for k in range(0, len(ids), 50):
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/videos", headers=H, timeout=40, params={
                "part": "snippet,statistics,contentDetails", "id": ",".join(ids[k:k + 50])}).json()
            for v in r.get("items", []):
                d = v["contentDetails"].get("duration", "")
                mm = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d) if d else None
                secs = sum(int(x or 0) * m for x, m in zip(mm.groups(), (86400, 3600, 60, 1))) if mm else 0
                out.append({"title": v["snippet"]["title"][:90], "views": int(v["statistics"].get("viewCount", 0)),
                            "type": "long" if secs >= 180 else "short"})
        except Exception:
            pass
    out.sort(key=lambda x: -x["views"])
    return out[:40]


def web_trends(desc, keys):
    q = (f"Search the web now. Niche: {desc}. Which videos in this niche are going viral THIS WEEK on Facebook "
         "(Reels and long videos), Instagram Reels, TikTok and YouTube (Shorts and long videos)? Which exact topics, "
         "stories, formats, video lengths and hook styles are getting the most views right now, and what events, "
         "seasons or festivals coming up in the next 2 weeks will people search for? Give specific names. Short plain text.")
    for key in keys:
        for m in ("gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash-lite"):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}",
                                  timeout=120, json={"contents": [{"parts": [{"text": q}]}],
                                                     "tools": [{"google_search": {}}]})
                if r.status_code == 200:
                    return "".join(p.get("text", "") for p in
                                   r.json()["candidates"][0]["content"]["parts"])[:3500]
            except Exception:
                pass
    return ""


def _gem_keys():
    ks = [os.environ.get(k) for k in sorted(os.environ) if k.endswith("GEMINI_API_KEY")]
    return [k for k in dict.fromkeys(ks) if k]


def get(bot):
    """Aaj ki trend report (cache se, warna nayi). {'date','youtube','web'}"""
    b, niche = _niche(bot)
    if not niche:
        return {}
    today = datetime.date.today().isoformat()
    path = os.path.join(DIR, f"{b}.json")
    try:
        c = json.load(open(path, encoding="utf-8"))
        if c.get("date") == today and (c.get("youtube") or c.get("web")):
            return c
    except Exception:
        pass
    desc, queries = niche
    c = {"date": today, "youtube": youtube_top(queries), "web": web_trends(desc, _gem_keys())}
    print(f"[trend_scout] {b}: {len(c['youtube'])} YouTube videos, web {len(c['web'])} chars", flush=True)
    if c["youtube"] or c["web"]:
        try:
            os.makedirs(DIR, exist_ok=True)
            json.dump(c, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass
    return c


def text(bot):
    try:
        c = get(bot)
    except Exception:
        return ""
    if not c or not (c.get("youtube") or c.get("web")):
        return ""
    yt = "\n".join(f"- [{v['type']}] {v['title']} ({v['views']:,} views)" for v in (c.get("youtube") or [])[:20])
    return f"""
WHAT PEOPLE ARE WATCHING RIGHT NOW (your own daily research, {c['date']}) - use it to choose today's topic/angle,
for reels AND long videos alike:
Most-viewed videos of the last 7 days in this niche:
{yt or "- n/a"}
What is viral this week on Facebook/Instagram/TikTok/YouTube:
{(c.get('web') or 'n/a').strip()}
-> Follow these trends where they fit the page and all the rules above (same kind of topic, story, hook or format -
never copy a title). Change the topic every day - do not pick the same trend two days in a row.
"""
