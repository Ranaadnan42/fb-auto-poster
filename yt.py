"""
YouTube upload (dono FB pages ke apne YouTube channels ke liye).
Har channel ka apna refresh token secret:
   Islamic Motivational Videos -> YT_ISLAMIC_REFRESH_TOKEN
   Hansi Ka Adda               -> YT_FUNNY_REFRESH_TOKEN
Client ID/secret: YT_<NAME>_CLIENT_ID / YT_<NAME>_CLIENT_SECRET, warna common YT_CLIENT_ID / YT_CLIENT_SECRET.
(Har channel ka alag Google Cloud project behtar hai - har project ko roz ka alag 10,000 quota milta hai.)
Token na ho to YouTube upload chup chaap skip - Facebook posting par koi asar nahi.
"""
import os
import re
import json
import time

import requests


def _creds(name):
    n = name.upper()
    cid = os.environ.get(f"YT_{n}_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get(f"YT_{n}_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
    ref = os.environ.get(f"YT_{n}_REFRESH_TOKEN")
    return cid, sec, ref


def enabled(name):
    return all(_creds(name))


def _token(name):
    cid, sec, ref = _creds(name)
    j = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "client_id": cid, "client_secret": sec, "refresh_token": ref,
        "grant_type": "refresh_token"}).json()
    if "access_token" not in j:
        raise RuntimeError(f"YouTube login fail: {j}")
    return j["access_token"]


def _clean_title(t):
    t = re.sub(r"[<>]", "", (t or "").replace("\n", " ")).strip()
    return t[:100] or "Video"


def upload(name, path, title, description, short=False, lang="ur", category="22"):
    """Video upload karta hai. Wapas: video id. category 22 = People & Blogs, 23 = Comedy."""
    token = _token(name)
    tags = [t.lstrip("#") for t in re.findall(r"#\w+", description or "")][:15]
    if short and "#shorts" not in title.lower():
        title = f"{title[:88]} #Shorts"
    meta = {"snippet": {"title": _clean_title(title), "description": (description or "")[:4900],
                        "tags": tags, "categoryId": category,
                        "defaultLanguage": lang, "defaultAudioLanguage": lang},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": True}}
    size = os.path.getsize(path)
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        data=json.dumps(meta), timeout=60)
    if r.status_code != 200 or "Location" not in r.headers:
        raise RuntimeError(f"YouTube upload start fail: {r.status_code} {r.text[:300]}")
    loc = r.headers["Location"]
    for attempt in range(4):
        try:
            with open(path, "rb") as f:
                r = requests.put(loc, data=f, timeout=1800, headers={
                    "Authorization": f"Bearer {token}", "Content-Type": "video/mp4"})
            if r.status_code in (200, 201):
                vid = r.json()["id"]
                print(f"YouTube ({name}) uploaded: https://youtu.be/{vid}", flush=True)
                return vid
            print(f"YouTube upload {r.status_code}: {r.text[:300]}", flush=True)
            if r.status_code in (400, 401, 403):
                break
        except Exception as e:
            print(f"YouTube upload retry {attempt + 1}: {str(e)[:150]}", flush=True)
        time.sleep(10)
    raise RuntimeError("YouTube upload fail")
