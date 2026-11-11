"""
News Act / Sports Hubs ka jaiza: page settings, aakhri posts + views, aur aakhri videos/reels
ke frames (contact sheet) review_out/ mein - taake asli quality dekhi ja sake.
"""
import json
import os
import subprocess

import requests

VER = "v23.0"
G = f"https://graph.facebook.com/{VER}"
OUT = "review_out"
os.makedirs(OUT, exist_ok=True)

PAGES = {
    "news": (os.environ.get("NEWS_PAGE_ID"), os.environ.get("NEWS_PAGE_TOKEN")),
    "sports": (os.environ.get("SPORTS_PAGE_ID"), os.environ.get("SPORTS_PAGE_TOKEN")),
}


def get(path, tok, **params):
    params["access_token"] = tok
    try:
        r = requests.get(f"{G}/{path}", params=params, timeout=60)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def sheet(url, dest):
    """Video ke 12 frames ek tasveer mein."""
    tmp = dest + ".mp4"
    try:
        with requests.get(url, stream=True, timeout=300) as r, open(tmp, "wb") as f:
            for c in r.iter_content(1 << 20):
                f.write(c)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                    "csv=p=0", tmp], capture_output=True, text=True).stdout.strip() or 0)
        if dur <= 0:
            return None
        fps = 12 / dur
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-vf",
                        f"fps={fps:.5f},scale=360:-2,tile=4x3", "-frames:v", "1", "-q:v", "4", dest], check=True)
        # awaaz ka pehla hissa bhi (sunne ke liye nahi, sirf maujood hai ya nahi)
        return round(dur, 1)
    except Exception as e:
        return f"error {e}"
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


report = {}
for key, (pid, tok) in PAGES.items():
    if not pid or not tok:
        report[key] = "secret missing"
        continue
    R = report[key] = {}
    R["page"] = get(pid, tok, fields="name,username,about,description,category,category_list,website,"
                                     "followers_count,fan_count,link,emails,phone,location,"
                                     "general_info,is_published,verification_status,picture{url},cover{source}")
    R["token"] = get("debug_token", tok, input_token=tok).get("data", {})
    R["token"] = {k: R["token"].get(k) for k in ("type", "expires_at", "data_access_expires_at", "scopes",
                                                  "is_valid")}
    posts = get(f"{pid}/posts", tok, limit=40, fields="message,created_time,permalink_url,status_type,"
                "attachments{media_type,title},shares,reactions.summary(true),comments.summary(true)")
    R["posts"] = [{"t": p.get("created_time"), "type": p.get("status_type"),
                   "media": ((p.get("attachments") or {}).get("data") or [{}])[0].get("media_type"),
                   "react": ((p.get("reactions") or {}).get("summary") or {}).get("total_count"),
                   "comments": ((p.get("comments") or {}).get("summary") or {}).get("total_count"),
                   "shares": (p.get("shares") or {}).get("count"),
                   "msg": (p.get("message") or "")[:700], "url": p.get("permalink_url")}
                  for p in posts.get("data", [])] or posts
    vids = get(f"{pid}/videos", tok, limit=12, fields="title,description,length,created_time,source,"
               "permalink_url,video_insights.metric(total_video_views,total_video_avg_time_watched)")
    R["videos"] = []
    for n, v in enumerate(vids.get("data", [])):
        ins = {i["name"]: (i.get("values") or [{}])[0].get("value")
               for i in ((v.get("video_insights") or {}).get("data") or [])}
        item = {"t": v.get("created_time"), "len": v.get("length"), "title": v.get("title"),
                "desc": (v.get("description") or "")[:500], "url": v.get("permalink_url"), "insights": ins}
        if n < 6 and v.get("source"):
            img = f"{OUT}/{key}_v{n}.jpg"
            item["sheet"] = img
            item["sheet_dur"] = sheet(v["source"], img)
        R["videos"].append(item)
    if not R["videos"]:
        R["videos_raw"] = vids

with open(f"{OUT}/report.json", "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1)[:20000])
