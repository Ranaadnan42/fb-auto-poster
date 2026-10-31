"""Reel post hone ke baad wahi video Facebook page ki STORY par bhi.

FB page video story: 9:16, 3-60 second. Reel 60s se lambi ho to pehle 59s kaat kar lagti hai.
Best-effort: story fail ho to sirf log/report - reel ka kaam nahi rukta.
"""
import os
import subprocess

import requests


def _fb(r):
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Facebook jawab samajh nahi aaya: {r.text[:300]}")
    if "error" in j:
        raise RuntimeError(f"Facebook story error: {j['error'].get('message', j)}")
    return j


def _duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except Exception:
        return 0.0


def _fit(path):
    """Story ke liye 59s se lambi video kaat do (re-encode nahi, sirf copy)."""
    if _duration(path) <= 59.5:
        return path
    out = os.path.splitext(path)[0] + "_story.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-t", "59", "-c", "copy",
                    "-movflags", "+faststart", out], check=True, timeout=300)
    return out


def post_story(page_id, token, path, ver="v23.0", log=print):
    """Video ko page story par lagata hai. Story post_id deta hai."""
    clip = _fit(path)
    base = f"https://graph.facebook.com/{ver}/{page_id}/video_stories"
    vid = _fb(requests.post(base, timeout=60, data={"upload_phase": "start",
                                                    "access_token": token}))["video_id"]
    with open(clip, "rb") as f:
        _fb(requests.post(f"https://rupload.facebook.com/video-upload/{ver}/{vid}",
                          headers={"Authorization": f"OAuth {token}", "offset": "0",
                                   "file_size": str(os.path.getsize(clip))}, data=f, timeout=1800))
    j = _fb(requests.post(base, timeout=120, data={"upload_phase": "finish", "video_id": vid,
                                                   "access_token": token}))
    sid = j.get("post_id") or vid
    log(f"Story posted: {sid}")
    return sid


def try_story(page_id, token, path, ver="v23.0", log=print, errors=None):
    try:
        return post_story(page_id, token, path, ver, log)
    except Exception as e:
        log(f"STORY ERROR (reel theek hai): {e}")
        if errors is not None:
            errors.append(f"story: {str(e)[:300]}")
        return None
