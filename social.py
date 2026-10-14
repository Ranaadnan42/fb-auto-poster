"""
Facebook reel ke baad wahi reel Instagram aur TikTok par bhi.
Koi secret/connection na ho to woh platform chup chaap skip - Facebook/YouTube par koi asar nahi.

INSTAGRAM (koi naya secret nahi):
  Instagram account "Professional" (Creator/Business) ho aur FB page se linked ho.
  Page token mein instagram_basic + instagram_content_publish permissions hon.
  Bot khud page se linked Instagram account dhoond leta hai.

TIKTOK (har page ka apna account):
  Secrets: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET (developers.tiktok.com app - sab accounts ke liye ek)
           TIKTOK_<NAME>_REFRESH_TOKEN   (NAME = ISLAMIC / FUNNY)
  App audit se pehle TikTok public post nahi karne deta - us waqt video TikTok app ke
  inbox/drafts mein bhej di jati hai (notification aata hai, ek tap se post).
  Refresh token banane ke liye:  python social.py tiktok-token <CODE> <REDIRECT_URI>

SNAPCHAT: Snapchat ka koi public posting API nahi - auto upload mumkin nahi.
"""
import os
import re
import sys
import time

import requests

GRAPH = "https://graph.facebook.com/v21.0"


def _clean_caption(text, max_tags=30, limit=2150):
    text = text or ""
    seen = 0

    def keep(m):
        nonlocal seen
        seen += 1
        return m.group(0) if seen <= max_tags else ""
    text = re.sub(r"#\w+", keep, text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return text[:limit]


# ------------------------------------------------------------- Instagram
def _ig_json(r):
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Instagram HTTP {r.status_code}: {r.text[:300]}")
    if "error" in j:
        raise RuntimeError(f"Instagram: {j['error'].get('message', j['error'])}")
    return j


def instagram_id(page_id, token):
    j = requests.get(f"{GRAPH}/{page_id}", timeout=60, params={
        "fields": "instagram_business_account", "access_token": token}).json()
    return (j.get("instagram_business_account") or {}).get("id")


def instagram_reel(page_id, token, path, caption, log=print):
    ig = instagram_id(page_id, token)
    if not ig:
        log("Instagram: page se koi Professional Instagram account linked nahi - skip")
        return None
    c = _ig_json(requests.post(f"{GRAPH}/{ig}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "share_to_feed": "true",
        "caption": _clean_caption(caption), "access_token": token}))
    cid = c["id"]
    with open(path, "rb") as f:
        r = requests.post(f"https://rupload.facebook.com/ig-api-upload/v21.0/{cid}", data=f,
                          timeout=1800, headers={"Authorization": f"OAuth {token}", "offset": "0",
                                                 "file_size": str(os.path.getsize(path))})
    if r.status_code >= 300:
        raise RuntimeError(f"Instagram upload HTTP {r.status_code}: {r.text[:300]}")
    for _ in range(60):                       # IG video process hone ka intezar (max ~10 min)
        time.sleep(10)
        s = _ig_json(requests.get(f"{GRAPH}/{cid}", timeout=60, params={
            "fields": "status_code,status", "access_token": token}))
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing fail: {s.get('status')}")
    else:
        raise RuntimeError("Instagram processing timeout")
    mid = _ig_json(requests.post(f"{GRAPH}/{ig}/media_publish", timeout=60, data={
        "creation_id": cid, "access_token": token}))["id"]
    log(f"Instagram reel posted: {mid}")
    return mid


# ---------------------------------------------------------------- TikTok
TT = "https://open.tiktokapis.com/v2"


def _tt_creds(name):
    return (os.environ.get("TIKTOK_CLIENT_KEY"), os.environ.get("TIKTOK_CLIENT_SECRET"),
            os.environ.get(f"TIKTOK_{name.upper()}_REFRESH_TOKEN"))


def tiktok_enabled(name):
    return all(_tt_creds(name))


def _tt_token(name):
    key, sec, ref = _tt_creds(name)
    j = requests.post(f"{TT}/oauth/token/", timeout=60, data={
        "client_key": key, "client_secret": sec, "grant_type": "refresh_token",
        "refresh_token": ref}).json()
    if "access_token" not in j:
        raise RuntimeError(f"TikTok login fail: {j}")
    return j["access_token"]


def _tt_json(r):
    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"TikTok HTTP {r.status_code}: {r.text[:300]}")
    err = j.get("error") or {}
    if err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok: {err.get('code')} - {err.get('message')}")
    return j.get("data") or {}


def _tt_upload(url, path):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        r = requests.put(url, data=f, timeout=1800, headers={
            "Content-Type": "video/mp4", "Content-Length": str(size),
            "Content-Range": f"bytes 0-{size - 1}/{size}"})
    if r.status_code >= 300:
        raise RuntimeError(f"TikTok upload HTTP {r.status_code}: {r.text[:300]}")


def _tiktok_caption(caption):
    """FB caption ko TikTok SEO ke mutabiq: keywords wali lines, TikTok CTA, sirf 5 hashtags."""
    paras = [x.strip() for x in (caption or "").split("\n\n") if x.strip()]
    tags = re.findall(r"#\w+", " ".join(p for p in paras if p.startswith("#")))
    text = [p for p in paras if not p.startswith("#") and "پیج" not in p and "page" not in p.lower()]
    keep, seen = [], set()
    for t in tags[:1] + [t for t in tags[1:] if t.lower() not in ("#reels", "#viral")][:3] + ["#fyp"]:
        if t.lower() not in seen:
            seen.add(t.lower())
            keep.append(t)
    text.append("Follow karein, roz nayi video 👈")
    return ("\n\n".join(text) + "\n\n" + " ".join(keep)).strip()[:2150]


def tiktok_upload(name, path, caption, log=print):
    caption = _tiktok_caption(caption)
    tok = _tt_token(name)
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    size = os.path.getsize(path)
    src = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
    mode = os.environ.get("TIKTOK_MODE", "direct")
    if mode == "direct":
        try:
            info = _tt_json(requests.post(f"{TT}/post/publish/creator_info/query/", headers=h,
                                          timeout=60))
            opts = info.get("privacy_level_options") or ["SELF_ONLY"]
            privacy = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in opts else opts[0]
            d = _tt_json(requests.post(f"{TT}/post/publish/video/init/", headers=h, timeout=60, json={
                "post_info": {"title": _clean_caption(caption, 20, 2150),
                              "privacy_level": privacy, "disable_comment": False,
                              "disable_duet": False, "disable_stitch": False},
                "source_info": src}))
            _tt_upload(d["upload_url"], path)
            log(f"TikTok posted ({privacy}): {d.get('publish_id')}")
            return d.get("publish_id")
        except RuntimeError as e:
            if "unaudited" not in str(e) and "scope" not in str(e):
                raise
            log(f"TikTok direct post abhi allowed nahi ({e}) - inbox mein bhej rahe hain")
    d = _tt_json(requests.post(f"{TT}/post/publish/inbox/video/init/", headers=h, timeout=60,
                               json={"source_info": src}))
    _tt_upload(d["upload_url"], path)
    log(f"TikTok inbox mein bhej di (app mein ek tap se post): {d.get('publish_id')}")
    return "inbox:" + str(d.get("publish_id"))


# ---------------------------------------------------------- dono ek saath
def share_reel(name, page_id, page_token, path, caption, entry, report, log=print):
    """FB reel ke baad Instagram + TikTok. Har error sirf report mein - run fail nahi hota."""
    if page_id and page_token and os.environ.get("INSTAGRAM_OFF") != "1":
        try:
            mid = instagram_reel(page_id, page_token, path, caption, log)
            if mid:
                entry["ig_id"] = mid
        except Exception as e:
            log(f"INSTAGRAM ERROR: {e}")
            report["errors"].append(f"instagram: {str(e)[:300]}")
    if tiktok_enabled(name):
        try:
            entry["tt_id"] = tiktok_upload(name, path, caption, log)
        except Exception as e:
            log(f"TIKTOK ERROR: {e}")
            report["errors"].append(f"tiktok: {str(e)[:300]}")


if __name__ == "__main__" and len(sys.argv) >= 4 and sys.argv[1] == "tiktok-token":
    # login ke baad redirect URL wala ?code=... yahan do -> refresh token milega (GitHub secret mein rakhein)
    j = requests.post(f"{TT}/oauth/token/", timeout=60, data={
        "client_key": os.environ["TIKTOK_CLIENT_KEY"], "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
        "code": sys.argv[2], "grant_type": "authorization_code", "redirect_uri": sys.argv[3]}).json()
    print(j.get("refresh_token") or j)
