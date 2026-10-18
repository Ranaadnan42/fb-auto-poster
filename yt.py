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


FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
SUB_LINE = {"ur": "🔔 روزانہ نئی ویڈیوز کے لیے چینل سبسکرائب کریں اور بیل آئیکن دبائیں",
            "en": "🔔 Subscribe and turn on the bell for a new video every day"}


def _seo_tags(description):
    """Hashtags + 'keywords | line' dono se YouTube tags (max ~450 chars)."""
    tags = [t.lstrip("#") for t in re.findall(r"#\w+", description or "")]
    for line in (description or "").splitlines():
        if "|" in line:
            tags += [k.strip() for k in line.split("|") if 1 < len(k.strip()) < 40]
    out, seen, total = [], set(), 0
    for t in tags:
        if t.lower() in seen:
            continue
        if total + len(t) + 2 > 450:
            break
        seen.add(t.lower()); out.append(t); total += len(t) + 2
    return out


def make_thumbnail(path, title, out, lang="ur"):
    """Video ke beech ke frame se 1280x720 thumbnail + bara peela title (libass - Urdu theek)."""
    import subprocess
    try:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                    "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip())
    except Exception:
        dur = 10.0
    words = re.sub(r"#\w+", "", title or "").split()[:9]
    half = (len(words) + 1) // 2
    text = " ".join(words[:half]) + ("\\N" + " ".join(words[half:]) if words[half:] else "")
    font = "Noto Naskh Arabic" if lang == "ur" else "Noto Sans"
    ass = out + ".ass"
    with open(ass, "w", encoding="utf-8") as f:
        f.write(f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T,{font},92,&H0000E6FF,&H0000E6FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,7,4,2,50,50,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:10.00,T,,0,0,0,,{text}
""")
    fd = f":fontsdir={FONTS_DIR}" if os.path.isdir(FONTS_DIR) else ""
    vf = ("scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
          f"eq=contrast=1.15:saturation=1.35,subtitles={ass}{fd}")
    subprocess.run(["ffmpeg", "-y", "-ss", f"{dur * 0.35:.2f}", "-i", path, "-vf", vf,
                    "-frames:v", "1", "-q:v", "3", out], check=True, capture_output=True)
    return out


def set_thumbnail(name, video_id, img):
    token = _token(name)
    with open(img, "rb") as f:
        r = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
                          data=f.read(), timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"thumbnail {r.status_code}: {r.text[:200]}")
    print(f"YouTube ({name}) thumbnail set", flush=True)


def upload(name, path, title, description, short=False, lang="ur", category="22"):
    """Video upload karta hai (SEO tags + subscribe line + lambi video par auto thumbnail). Wapas: video id."""
    token = _token(name)
    tags = _seo_tags(description)
    sub = SUB_LINE.get(lang, SUB_LINE["en"])
    if sub not in (description or ""):
        description = f"{description or ''}\n\n{sub}".strip()
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
                try:
                    thumb = make_thumbnail(path, title, f"yt_thumb_{vid}.jpg", lang)
                    set_thumbnail(name, vid, thumb)
                except Exception as e:
                    print(f"thumbnail skip: {str(e)[:200]}", flush=True)
                return vid
            print(f"YouTube upload {r.status_code}: {r.text[:300]}", flush=True)
            if r.status_code in (400, 401, 403):
                break
        except Exception as e:
            print(f"YouTube upload retry {attempt + 1}: {str(e)[:150]}", flush=True)
        time.sleep(10)
    raise RuntimeError("YouTube upload fail")
