"""Har page par pichhle 4 din mein roz kitni photo / reel / lambi video / story lagi (sirf check)."""
import os, datetime as dt, requests
G = "https://graph.facebook.com/v23.0"
PK = dt.timezone(dt.timedelta(hours=5))
PAGES = [("Islamic", "FB_PAGE_ID", "FB_PAGE_TOKEN"), ("Hansi Ka Adda", "FUNNY_PAGE_ID", "FUNNY_PAGE_TOKEN"),
         ("Legends/Cinematic", "CINE_FB_PAGE_ID", "CINE_FB_TOKEN"), ("Frames of Life", "FRAMES_PAGE_ID", "FRAMES_PAGE_TOKEN"),
         ("Web Builder", "WB_PAGE_ID", "WB_PAGE_TOKEN")]
start = (dt.datetime.now(PK) - dt.timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
since = int(start.timestamp())


def get(path, tok, **p):
    p["access_token"] = tok
    out, url = [], f"{G}/{path}"
    while url and len(out) < 500:
        j = requests.get(url, params=p, timeout=60).json()
        if "error" in j:
            raise RuntimeError(j["error"].get("message", "")[:150])
        out += j.get("data", [])
        url, p = (j.get("paging") or {}).get("next"), {}
    return out


def day(t):
    if isinstance(t, (int, float)) or str(t).isdigit():
        d = dt.datetime.fromtimestamp(float(t), dt.timezone.utc)
    else:
        d = dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S%z")
    return d.astimezone(PK).strftime("%m-%d") if d >= start else None


for name, pid_k, tok_k in PAGES:
    pid, tok = os.environ.get(pid_k, "").strip(), os.environ.get(tok_k, "").strip()
    if not (pid and tok):
        print(f"\n## {name}: secret nahi"); continue
    rows = {}
    add = lambda d, k: d and rows.setdefault(d, {"photo": 0, "reel": 0, "long": 0, "story": 0, "text": 0}).__setitem__(k, rows[d][k] + 1)
    err = []
    seen = set()
    for ep in ("video_reels", "videos"):
        try:
            for v in get(f"{pid}/{ep}", tok, since=since, limit=100, fields="id,created_time,length"):
                if v["id"] in seen: continue
                seen.add(v["id"])
                add(day(v["created_time"]), "long" if float(v.get("length") or 0) > 90 else "reel")
        except Exception as e: err.append(f"{ep}: {e}")
    try:
        for p in get(f"{pid}/published_posts", tok, since=since, limit=100, fields="created_time,attachments{media_type,type}"):
            att = (p.get("attachments") or {}).get("data", [])
            if any(a.get("media_type") == "photo" or a.get("type") in ("photo", "album") for a in att):
                add(day(p["created_time"]), "photo")
            elif not att:
                add(day(p["created_time"]), "text")
    except Exception as e: err.append(f"posts: {e}")
    try:
        for s in get(f"{pid}/stories", tok, since=since, limit=100):
            if (s.get("status") or "PUBLISHED").upper() == "PUBLISHED":
                add(day(s.get("creation_time") or 0), "story")
    except Exception as e: err.append(f"stories: {e}")
    print(f"\n## {name}")
    print("din    photo reel lambi story text")
    for d in sorted(rows):
        r = rows[d]; print(f"{d}  {r['photo']:5} {r['reel']:4} {r['long']:5} {r['story']:5} {r['text']:4}")
    for e in err: print("  !", e)
