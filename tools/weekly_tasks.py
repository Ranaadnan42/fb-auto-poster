"""
Weekly Tasks agent - Facebook ke "This week's tasks" (reels + photo posts) hafte se 1 din PEHLE poore karna.

FB hafta: Itwaar se Hafta. Hamari deadline: Jumma raat (Pakistan) = hafte ka 6th din khatam.
Tasks: posts (photos), reels, stories. Story har reel ke saath khud lagti hai; stories kam hon to extra reel chalti hai.
Har run (din mein 2 dafa, ai_employee.yml ke andar):
  1. Is hafte page par kitni reels aur photo posts lag chuki (Graph API se ginti).
  2. Roz ke schedule se deadline tak kitni aur lagengi.
  3. Kami ho -> abhi extra runs chala do (photos.yml / main.yml / funny.yml), taake Jumme tak target poora.
Targets weekly_targets.json mein - har hafte ek browser agent (Claude scheduled task) Facebook ka Page status
khud parh kar likhta hai. Agar is hafte abhi nahi parhe gaye to pichhle hafte se 20% zyada maan kar kaam chalta hai.
"""
import os
import sys
import json
import math
import datetime as dt

import requests

sys.path.insert(0, os.path.dirname(__file__))
import ghapi      # noqa: E402

GRAPH = "https://graph.facebook.com/v23.0"
PK = dt.timezone(dt.timedelta(hours=5))
NOW = dt.datetime.now(dt.timezone.utc)
TARGETS_FILE = "weekly_targets.json"
OUT = "weekly_tasks.json"
MAX_EXTRA = 1            # har page par ek run mein sirf 1 extra post (din mein 2 run = roz max 2 extra) - reach kharab na ho

# page -> secrets, roz ka schedule (FB par), extra post kaise chalani hai (list = baari baari)
PAGES = {
    "islamic": dict(id="FB_PAGE_ID", tok="FB_PAGE_TOKEN", daily_photos=4, daily_reels=2,
                    photo=[("photos.yml", {"pages": "islamic", "slot": "1"})],
                    reel=[("main.yml", {"language": "ur", "post_type": "reel"})]),
    "funny": dict(id="FUNNY_PAGE_ID", tok="FUNNY_PAGE_TOKEN", daily_photos=5, daily_reels=3,
                  photo=[("photos.yml", {"pages": "funny", "slot": "1"})],
                  reel=[("funny.yml", {"mode": "reel"})]),
    "frames": dict(id="FRAMES_PAGE_ID", tok="FRAMES_PAGE_TOKEN", daily_photos=1, daily_reels=2,
                   photo=[("photos.yml", {"pages": "frames", "slot": "2"})],
                   reel=[("frames.yml", {"mode": "short", "dry_run": "false"})]),
    "webbuilder": dict(id="WB_PAGE_ID", tok="WB_PAGE_TOKEN", daily_photos=3, daily_reels=3,
                       photo=[("webbuilder.yml", {"mode": m}) for m in ("pic_ar", "pic_en", "pic_ur")],
                       reel=[("webbuilder.yml", {"mode": m}) for m in ("reel_ar", "reel_en", "reel_ur")]),
}
DEFAULT_TARGETS = {"reels": 0, "photos": 0}   # "stories" na ho to = reels
GROW = 1.2          # naye hafte ke targets abhi parhe nahi gaye -> pichhle hafte se 20% zyada maan lo


def env(k):
    return (os.environ.get(k) or "").strip()


def fb(path, token, **params):
    params["access_token"] = token
    j = requests.get(f"{GRAPH}/{path}", params=params, timeout=60).json()
    if "error" in j:
        raise RuntimeError(j["error"].get("message", str(j["error"]))[:200])
    return j


def week_bounds():
    pk = NOW.astimezone(PK)
    start = (pk - dt.timedelta(days=(pk.weekday() + 1) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    deadline = start + dt.timedelta(days=6)          # Jumma raat 12 baje (Pakistan)
    return start, deadline


def count(pid, token, start):
    since = int(start.timestamp())
    photos = 0
    posts = fb(f"{pid}/published_posts", token, since=since, limit=100,
               fields="created_time,attachments{media_type,type}").get("data", [])
    for p in posts:
        att = (p.get("attachments") or {}).get("data", [])
        if any((a.get("media_type") == "photo" or a.get("type") == "photo") for a in att):
            photos += 1
    reels = 0
    try:
        vids = fb(f"{pid}/video_reels", token, since=since, limit=100, fields="created_time").get("data", [])
        reels = sum(1 for v in vids
                    if dt.datetime.strptime(v["created_time"], "%Y-%m-%dT%H:%M:%S%z") >= start)
    except Exception:
        reels = -1
    return photos, reels


def count_stories(pid, token, start):
    """Is hafte page par kitni stories lagi (har reel ke saath story bhi lagti hai)."""
    try:
        data = fb(f"{pid}/stories", token, since=int(start.timestamp()), limit=100).get("data", [])
    except Exception:
        return -1
    n = 0
    for st in data:
        try:
            t = float(st.get("creation_time") or 0)
        except Exception:
            t = dt.datetime.strptime(st["creation_time"], "%Y-%m-%dT%H:%M:%S%z").timestamp()
        if t >= start.timestamp() and (st.get("status") or "PUBLISHED").upper() == "PUBLISHED":
            n += 1
    return n


def dispatch(options, n):
    ok = 0
    for i in range(n):
        wf, inputs = options[i % len(options)]
        try:
            ghapi.call("POST", f"/actions/workflows/{wf}/dispatches", {"ref": "main", "inputs": inputs})
            ok += 1
        except Exception as e:
            print(f"   dispatch fail {wf}: {str(e)[:120]}", flush=True)
    return ok


def main():
    try:
        targets = json.load(open(TARGETS_FILE, encoding="utf-8"))
    except Exception:
        targets = {}
    start, deadline = week_bounds()
    fresh = targets.get("week") == start.date().isoformat()
    if not fresh:      # is hafte ke tasks abhi browser agent ne nahi parhe - pichhle se zyada rakh lo
        targets = {k: ({kk: math.ceil(vv * GROW) for kk, vv in v.items()} if isinstance(v, dict) else v)
                   for k, v in targets.items()}
    days_left = max(0.0, (deadline - NOW).total_seconds() / 86400)
    rec = {"at": NOW.isoformat(timespec="minutes"), "week_start": start.date().isoformat(),
           "deadline_pk": deadline.isoformat(timespec="minutes"),
           "targets_fresh": fresh, "pages": {}}
    for name, cfg in PAGES.items():
        pid, token = env(cfg["id"]), env(cfg["tok"])
        if not (pid and token):
            continue
        t = {**DEFAULT_TARGETS, **(targets.get(name) or {})}
        try:
            photos, reels = count(pid, token, start)
        except Exception as e:
            rec["pages"][name] = {"error": str(e)}
            continue
        stories = count_stories(pid, token, start)
        t.setdefault("stories", t["reels"])          # target na likha ho to: jitni reels utni stories
        r = {"photos": f"{photos}/{t['photos']}", "reels": f"{reels}/{t['reels']}",
             "stories": f"{stories}/{t['stories']}", "extra": []}
        left = MAX_EXTRA
        # story alag se nahi banti - har reel post hote hi wahi video story par bhi lagti hai (stories.py)
        for kind, done, daily in (("reels", reels, cfg["daily_reels"]), ("stories", stories, cfg["daily_reels"]),
                                  ("photos", photos, cfg["daily_photos"])):   # pehle reel (reach zyada)
            if done < 0 or days_left <= 0:
                continue
            coming = math.floor(daily * days_left * 0.85)      # 15% margin - koi post fail bhi ho jaye
            short = t[kind] - done - coming
            if kind == "stories" and short > 0:
                short -= sum(int(x.split()[1]) for x in r["extra"] if x.startswith("reels:"))  # extra reels = extra stories
            if short > 0 and left > 0:
                n = dispatch(cfg["photo" if kind == "photos" else "reel"], min(short, left))
                left -= n
                r["extra"].append(f"{kind}: {n} extra chala di (kami {short})")
        rec["pages"][name] = r
        print(f"== {name}: {r}", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
