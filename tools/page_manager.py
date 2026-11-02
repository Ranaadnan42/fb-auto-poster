"""
Page Manager - AI employee ka Facebook pages wala hissa (din mein 2 dafa, ai_employee.yml ke andar).

Har FB page par (jis ka secret ho):
  1. Token zinda hai ya nahi (mara ho to record mein likho, AI agent dekhta hai).
  2. Page profile ki zaroori settings: bio (about), description, website - KHALI ho to khud bhar do
     (jo pehle se likha hai use kabhi nahi chhedta).
  3. Monetization tracking: followers + 28 din ke views/engagement (Facebook insights), har din ka
     record taake pata chale page monetization ki taraf barh raha hai ya ruka hua hai.
  4. Posting ruk gayi? (30 ghante se koi post nahi) -> us page ka bot khud chala do (din mein 1 dafa).
Sab kuch page_manager.json mein. Koi email/report user ko nahi.
"""
import os
import sys
import json
import datetime as dt

import requests

sys.path.insert(0, os.path.dirname(__file__))
import ghapi      # noqa: E402

GRAPH = "https://graph.facebook.com/v23.0"
OUT = "page_manager.json"
NOW = dt.datetime.now(dt.timezone.utc)
SITE = "https://client-hunt-six.vercel.app/"

# page -> (id secret, token secret, uska posting workflow, profile ki default settings)
PAGES = {
    "islamic": ("FB_PAGE_ID", "FB_PAGE_TOKEN", "main.yml", {
        "about": "Daily Islamic reminders, Quran & Hadith motivation in Urdu. Like, share & follow - "
                 "neki phelana sadqa-e-jariya hai.",
        "description": "Islamic Motivational Videos - roz nayi Islamic motivational reels, videos aur "
                       "posts: Quran, Hadith, Seerat, duas aur zindagi ke sabaq, Urdu mein.",
    }),
    "funny": ("FUNNY_PAGE_ID", "FUNNY_PAGE_TOKEN", "funny.yml", {
        "about": "Hansi Ka Adda - roz naye funny videos, comedy reels aur memes. Hanso aur hansao!",
        "description": "Hansi Ka Adda | ہنسی کا اڈا - Pakistani comedy, funny reels, cartoon aur viral "
                       "hansi wali videos, har roz. Follow karein aur doston ko tag karein.",
    }),
    "legends": ("CINE_FB_PAGE_ID", "CINE_FB_TOKEN", "cinematic.yml", {
        "about": "Legends Untold - epic fantasy stories, myths and legends, told cinematically every day.",
        "description": "Legends Untold brings you new cinematic fantasy stories daily - heroes, kingdoms, "
                       "dragons and forgotten legends. Follow for a new story every day.",
    }),
    "frames": ("FRAMES_PAGE_ID", "FRAMES_PAGE_TOKEN", "frames.yml", {
        "about": "Frames of Life - documentaries about countries, cities, cultures, food and people.",
        "description": "Frames of Life: real-footage documentaries about every country and city - history, "
                       "culture, food, music and how people live. New videos every day.",
    }),
    "webbuilder": ("WB_PAGE_ID", "WB_PAGE_TOKEN", "webbuilder.yml", {
        "about": "POS software, websites & mobile apps for businesses in Saudi Arabia, UAE & Pakistan. "
                 "WhatsApp +92 307 5267349",
        "description": "Web Builder - POS software (offline, for shops & restaurants), business websites "
                       "and mobile apps. Serving Saudi Arabia, UAE, Pakistan and worldwide.",
        "website": SITE,
    }),
}
# Facebook kabhi kabhi metric naam badalta hai - jo chale wohi le lo
METRICS = ["page_follows", "page_media_view", "page_total_media_view_unique",
           "page_post_engagements", "page_video_views", "page_impressions_unique"]


def env(k):
    return (os.environ.get(k) or "").strip()


def fb(method, path, token, **params):
    params["access_token"] = token
    r = requests.request(method, f"{GRAPH}/{path}", params=params if method == "GET" else None,
                         data=params if method != "GET" else None, timeout=60)
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"].get("message", str(j["error"]))[:200])
    return j


def load():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def check_page(name, pid, token, workflow, defaults, rec):
    out = {"at": NOW.isoformat(timespec="minutes"), "done": [], "problems": []}
    # 1. token + profile
    try:
        info = fb("GET", pid, token, fields="name,followers_count,fan_count,about,description,website,"
                                            "category,is_published,link")
    except Exception as e:
        out["problems"].append(f"token/page nahi khula: {e}")
        return out
    out["name"] = info.get("name")
    out["followers"] = info.get("followers_count") or info.get("fan_count") or 0
    if info.get("is_published") is False:
        out["problems"].append("page unpublished hai")

    # 2. khali settings bharo (pehle se likhi cheez nahi chhedni)
    fill = {k: v for k, v in defaults.items() if not (info.get(k) or "").strip()}
    for k, v in fill.items():
        try:
            fb("POST", pid, token, **{k: v})
            out["done"].append(f"{k} khali tha - bhar diya")
        except Exception as e:
            out["problems"].append(f"{k} set nahi hua: {str(e)[:120]}")

    # 3. insights (28 din)
    stats = {}
    for m in METRICS:
        try:
            d = fb("GET", f"{pid}/insights", token, metric=m, period="days_28").get("data", [])
            vals = (d[0].get("values") or []) if d else []
            if vals:
                stats[m] = vals[-1].get("value")
        except Exception:
            pass
    out["insights_28d"] = stats
    hist = rec.get(name, {}).get("history", [])
    hist = [h for h in hist if h.get("day") != NOW.date().isoformat()][-59:]
    hist.append({"day": NOW.date().isoformat(), "followers": out["followers"], **stats})
    out["history"] = hist
    if len(hist) >= 8 and hist[-1]["followers"] <= hist[-8]["followers"]:
        out["problems"].append("7 din se followers nahi barhe - content badalna chahiye")

    # 4. posting ruki to bot chalao (din mein 1 dafa)
    try:
        posts = fb("GET", f"{pid}/published_posts", token, limit=5, fields="created_time").get("data", [])
    except Exception:
        posts = fb("GET", f"{pid}/feed", token, limit=5, fields="created_time").get("data", [])
    last = max((dt.datetime.strptime(p["created_time"], "%Y-%m-%dT%H:%M:%S%z") for p in posts), default=None)
    out["last_post"] = last.isoformat(timespec="minutes") if last else None
    gap = (NOW - last).total_seconds() / 3600 if last else 999
    if gap > 30:
        prev = rec.get(name, {}).get("kicked")
        if prev != NOW.date().isoformat():
            try:
                ghapi.call("POST", f"/actions/workflows/{workflow}/dispatches", {"ref": "main"})
                out["done"].append(f"{int(gap)} ghante se post nahi thi - {workflow} khud chala diya")
                out["kicked"] = NOW.date().isoformat()
            except Exception as e:
                out["problems"].append(f"{int(gap)} ghante se post nahi, bot chal na saka: {str(e)[:80]}")
        else:
            out["kicked"] = prev
            out["problems"].append(f"{int(gap)} ghante se post nahi (aaj bot chalaya ja chuka)")
    return out


def main():
    rec = load()
    for name, (id_k, tok_k, wf, defaults) in PAGES.items():
        pid, token = env(id_k), env(tok_k)
        if not (pid and token):
            continue
        print(f"== {name}", flush=True)
        try:
            rec[name] = check_page(name, pid, token, wf, defaults, rec)
        except Exception as e:
            rec.setdefault(name, {})["problems"] = [f"check fail: {str(e)[:150]}"]
        r = rec[name]
        print(f"   followers {r.get('followers')} | {r.get('insights_28d')} | done {r.get('done')} "
              f"| problems {r.get('problems')}", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
