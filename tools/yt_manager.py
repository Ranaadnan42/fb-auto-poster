"""
YouTube Manager - Super Manager ka YouTube hissa (din mein 2 dafa, ai_employee.yml ke andar).
Har channel (jis ka token ho): subscribers, total views, videos, aakhri upload kab, 24 ghante mein kitni uploads,
token zinda hai ya nahi. Sab yt_manager.json mein -> Supabase Super Manager WhatsApp report mein dikhata hai.
Upload 30 ghante se ruki ho to us channel ka bot khud chala deta hai (din mein 1 dafa).
"""
import os
import sys
import json
import datetime as dt

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import yt        # noqa: E402
import ghapi     # noqa: E402

OUT = "yt_manager.json"
NOW = dt.datetime.now(dt.timezone.utc)
API = "https://www.googleapis.com/youtube/v3"
# yt.py ka naam -> (channel ka naam report ke liye, us ka bot)
CHANNELS = {
    "islamic": ("Islamic Motivational Videos (YT)", "main.yml"),
    "funny": ("Hansi Ka Adda (YT)", "funny.yml"),
    "frames": ("Frames of Life (YT)", "frames.yml"),
    "world": ("Atlas Untold (YT)", "world.yml"),
    "default": ("Legends Untold (YT)", "cinematic.yml"),
    "movie": ("Movie/2nd channel (YT)", None),      # Movie Recaps bot ruka hua hai - khud nahi chalana
}
if os.environ.get("YT_REFRESH_TOKEN") and not os.environ.get("YT_DEFAULT_REFRESH_TOKEN"):
    os.environ["YT_DEFAULT_REFRESH_TOKEN"] = os.environ["YT_REFRESH_TOKEN"]   # Legends Untold ka token


def check(name, label, wf, rec):
    out = {"name": label, "at": NOW.isoformat(timespec="minutes"), "done": [], "problems": []}
    try:
        tok = yt._token(name)
    except Exception as e:
        out["problems"].append(f"YouTube login/token fail: {str(e)[:120]}")
        return out
    h = {"Authorization": f"Bearer {tok}"}
    ch = requests.get(f"{API}/channels", headers=h, timeout=60,
                      params={"part": "snippet,statistics,contentDetails", "mine": "true"}).json()
    if ch.get("error") or not ch.get("items"):
        # token sirf upload ki ijazat wala - stats nahi parh sakte; ghalat "999 ghante" par agent mat chalao
        err = (ch.get("error") or {}).get("message", "channel nahi mila")
        out["problems"].append(f"stats parhne ki ijazat nahi (token sirf upload): {str(err)[:90]}")
        out["no_stats"] = True
        return out
    it = (ch.get("items") or [{}])[0]
    st = it.get("statistics", {})
    out["title"] = it.get("snippet", {}).get("title")
    out["subscribers"] = int(st.get("subscriberCount", 0) or 0)
    out["views"] = int(st.get("viewCount", 0) or 0)
    out["videos"] = int(st.get("videoCount", 0) or 0)
    up = it.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    times = []
    if up:
        pl = requests.get(f"{API}/playlistItems", headers=h, timeout=60,
                          params={"part": "contentDetails", "playlistId": up, "maxResults": 25}).json()
        for x in pl.get("items", []):
            t = x.get("contentDetails", {}).get("videoPublishedAt")
            if t:
                times.append(dt.datetime.fromisoformat(t.replace("Z", "+00:00")))
    # recent videos ke views -> top video + average (market tools jaisi analytics)
    try:
        ids = [x.get("contentDetails", {}).get("videoId") for x in (pl.get("items", []) if up else [])]
        ids = [i for i in ids if i]
        if ids:
            vs = requests.get(f"{API}/videos", headers=h, timeout=60,
                              params={"part": "snippet,statistics", "id": ",".join(ids[:25])}).json().get("items", [])
            vv = sorted(((int(v.get("statistics", {}).get("viewCount", 0) or 0),
                          v.get("snippet", {}).get("title", "")[:70], v["id"]) for v in vs), reverse=True)
            if vv:
                out["recent_avg_views"] = round(sum(x[0] for x in vv) / len(vv))
                out["top_videos"] = [{"views": a, "title": b, "url": f"https://youtu.be/{c}"} for a, b, c in vv[:3]]
    except Exception as e:
        print("   video stats fail:", str(e)[:100], flush=True)
    last = max(times, default=None)
    out["last_upload"] = last.isoformat(timespec="minutes") if last else None
    out["uploads_24h"] = sum(1 for t in times if (NOW - t).total_seconds() < 86400)
    hist = [x for x in rec.get(name, {}).get("history", []) if x.get("day") != NOW.date().isoformat()][-59:]
    hist.append({"day": NOW.date().isoformat(), "subscribers": out["subscribers"], "views": out["views"]})
    out["history"] = hist
    gap = (NOW - last).total_seconds() / 3600 if last else 999
    if gap > 30 and wf:
        if rec.get(name, {}).get("kicked") != NOW.date().isoformat():
            try:
                ghapi.call("POST", f"/actions/workflows/{wf}/dispatches", {"ref": "main"})
                out["done"].append(f"{int(gap)} ghante se upload nahi thi - {wf} khud chala diya")
                out["kicked"] = NOW.date().isoformat()
            except Exception as e:
                out["problems"].append(f"{int(gap)} ghante se upload nahi, bot chal na saka: {str(e)[:80]}")
        else:
            out["kicked"] = rec[name]["kicked"]
            out["problems"].append(f"{int(gap)} ghante se upload nahi (aaj bot chalaya ja chuka)")
    return out


def main():
    try:
        rec = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        rec = {}
    for name, (label, wf) in CHANNELS.items():
        if not yt.enabled(name):
            continue
        print(f"== {name}", flush=True)
        try:
            rec[name] = check(name, label, wf, rec)
        except Exception as e:
            rec[name] = {"name": label, "at": NOW.isoformat(timespec="minutes"), "problems": [f"check fail: {str(e)[:150]}"]}
        print("  ", {k: v for k, v in rec[name].items() if k != "history"}, flush=True)
    json.dump(rec, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
