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
    # baaqi saare pages - settings pehle se set hain, sirf nigrani (followers, posting, ruka bot chalao)
    "news": ("NEWS_PAGE_ID", "NEWS_PAGE_TOKEN", "news.yml", {}),
    "newsur": ("NEWSUR_PAGE_ID", "NEWSUR_PAGE_TOKEN", "news.yml", {}),
    "sports": ("SPORTS_PAGE_ID", "SPORTS_PAGE_TOKEN", "news.yml", {}),
    "scenic": ("SCENIC_PAGE_ID", "SCENIC_PAGE_TOKEN", "scenic.yml", {}),
    "war": ("WAR_PAGE_ID", "WAR_PAGE_TOKEN", "war.yml", {}),
    "birds": ("BIRDS_PAGE_ID", "BIRDS_PAGE_TOKEN", "birds.yml", {}),
    "pets": ("PETS_PAGE_ID", "PETS_PAGE_TOKEN", "pets.yml", {}),
    "wild": ("WILD_PAGE_ID", "WILD_PAGE_TOKEN", "wildlife.yml", {}),
    "faizi": ("FAIZI_PAGE_ID", "FAIZI_PAGE_TOKEN", "faizi.yml", {}),
}
# Facebook kabhi kabhi metric naam badalta hai - jo chale wohi le lo
METRICS = ["page_media_view", "page_total_media_view_unique", "page_post_engagements",
           "page_video_views", "page_daily_follows_unique", "page_impressions_unique"]


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


PK = dt.timezone(dt.timedelta(hours=5))


def post_analytics(pid, token):
    """28 din ki posts: reactions+comments+shares. Best posting ghante (PK time) aur top posts."""
    since = int((NOW - dt.timedelta(days=28)).timestamp())
    fields = ("created_time,message,permalink_url,shares,"
              "reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)")
    posts, url, params = [], f"{GRAPH}/{pid}/published_posts", {"access_token": token, "fields": fields,
                                                                 "since": since, "limit": 100}
    for _ in range(6):
        j = requests.get(url, params=params, timeout=60).json()
        if "error" in j:
            raise RuntimeError(j["error"].get("message", "")[:150])
        posts += j.get("data", [])
        url, params = (j.get("paging") or {}).get("next"), None
        if not url:
            break
    rows = []
    for p in posts:
        e = ((p.get("reactions") or {}).get("summary") or {}).get("total_count", 0) + \
            ((p.get("comments") or {}).get("summary") or {}).get("total_count", 0) + \
            (p.get("shares") or {}).get("count", 0)
        t = dt.datetime.strptime(p["created_time"], "%Y-%m-%dT%H:%M:%S%z").astimezone(PK)
        rows.append((e, t, (p.get("message") or "").strip().replace("\n", " ")[:80], p.get("permalink_url")))
    if not rows:
        return {"posts_28d": 0, "eng_28d": 0}
    total = sum(r[0] for r in rows)
    by_h = {}
    for e, t, _, _ in rows:
        by_h.setdefault(t.hour, []).append(e)
    hours = sorted(((sum(v) / len(v), h) for h, v in by_h.items() if len(v) >= 2), reverse=True)
    top = sorted(rows, key=lambda r: -r[0])[:3]
    return {
        "posts_28d": len(rows), "eng_28d": total, "eng_avg": round(total / len(rows), 1),
        "best_hours_pk": [h for _, h in hours[:3]],
        "top_posts": [{"eng": e, "text": m, "url": u, "at": t.strftime("%d %b %H:%M")} for e, t, m, u in top],
        "low_posts": len([r for r in rows if r[0] == 0]),
    }


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
            if vals and vals[-1].get("value") is not None:
                stats[m] = vals[-1].get("value")
                continue
            # naye metric sirf "day" period dete hain -> 28 din jama karo
            d = fb("GET", f"{pid}/insights", token, metric=m, period="day",
                   since=int((NOW - dt.timedelta(days=28)).timestamp()),
                   until=int(NOW.timestamp())).get("data", [])
            vals = [v.get("value") for v in ((d[0].get("values") or []) if d else [])]
            nums = [v for v in vals if isinstance(v, (int, float))]
            if nums:
                stats[m] = sum(nums)
        except Exception:
            pass
    out["insights_28d"] = stats

    # 3b. apni ginti (market tools jaisi): 28 din ki har post ka engagement -> best time + top post
    try:
        out.update(post_analytics(pid, token))
    except Exception as e:
        print("   analytics fail:", str(e)[:120], flush=True)
    hist = rec.get(name, {}).get("history", [])
    hist = [h for h in hist if h.get("day") != NOW.date().isoformat()][-59:]
    hist.append({"day": NOW.date().isoformat(), "followers": out["followers"], "eng_28d": out.get("eng_28d"), **stats})
    out["history"] = hist
    if len(hist) >= 8 and hist[-1]["followers"] <= hist[-8]["followers"]:
        out["problems"].append("7 din se followers nahi barhe - content badalna chahiye")

    # 4. posting ruki to bot chalao (din mein 1 dafa)
    try:
        posts = fb("GET", f"{pid}/published_posts", token, limit=40, fields="created_time").get("data", [])
    except Exception:
        posts = fb("GET", f"{pid}/feed", token, limit=40, fields="created_time").get("data", [])
    out["posts_24h"] = sum(1 for p in posts if (NOW - dt.datetime.strptime(
        p["created_time"], "%Y-%m-%dT%H:%M:%S%z")).total_seconds() < 86400)
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
