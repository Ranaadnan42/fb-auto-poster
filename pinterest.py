"""
Pinterest Auto Pinner - YouTube videos ko Pinterest par pin karta hai (traffic YouTube par).

3 accounts (har ek ka apna Pinterest account, ek hi developer app):
  islamic -> Islamic Motivational Videos (sirf English videos - Pinterest par US/UK log)
  legends -> Legends Untold (fantasy stories)
  atlas   -> Atlas Untold (har mulk ka alag board)

Har pin: 1000x1500 khoobsurat tasveer (YouTube thumbnail + title) + link YouTube video par.
Pehle nayi videos, phir purani (evergreen) - har run mein har account se max PINS_PER_RUN.

Secrets: PINTEREST_APP_ID, PINTEREST_APP_SECRET,
         PINTEREST_{ISLAMIC,LEGENDS,ATLAS}_REFRESH_TOKEN  (docs/pinterest.html se milta hai)
Jis account ka token nahi - woh chup chaap skip. Pinterest naya refresh token deta hai -
woh pinterest_tokens.json mein encrypted (app secret se) save hota hai.
DRY_RUN=1 -> sirf dikhaye, pin na kare.
"""
import os
import io
import json
import time
import base64
import hashlib
import datetime
import textwrap

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

API = "https://api.pinterest.com/v5"
STATE_FILE = "pinterest_state.json"
TOKENS_FILE = "pinterest_tokens.json"
REPORT_FILE = "pinterest_last_run.json"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
PINS_PER_RUN = int(os.environ.get("PINS_PER_RUN") or 2)
MIN_AGE_HOURS = 1
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "NotoSans-Bold.ttf")
MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]

ACCOUNTS = {
    "islamic": {
        "name": "Islamic Motivational Videos",
        "sources": [("history.json", "long_yt", False), ("history.json", "reel_yt", True)],
        "only_en": True,
        "board": lambda e: "Islamic Reminders",
        "board_desc": "Daily Islamic reminders: patience, dua, Quran wisdom and stories of the prophets.",
        "about": "Islamic motivational reminders for Muslims worldwide",
    },
    "legends": {
        "name": "Legends Untold",
        "sources": [("cinematic_en_long_history.json", "yt_id", False),
                    ("cinematic_en_short_history.json", "yt_id", True)],
        "board": lambda e: "Fantasy Stories & Legends",
        "board_desc": "Animated fantasy stories, dragons, lost temples and epic legends.",
        "about": "animated fantasy story videos (dragons, magic, adventure)",
    },
    "atlas": {
        "name": "Atlas Untold",
        "sources": [("world_long_history.json", "yt_id", False),
                    ("world_short_history.json", "yt_id", True)],
        "board": lambda e: f"{(e.get('subject') or 'World').split(',')[-1].strip()} Travel & Life",
        "board_desc": "Travel documentaries: cost of living, culture, safety and daily life.",
        "about": "travel and country documentaries (cost of living, culture, daily life)",
    },
}

REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "dry_run": DRY_RUN,
          "accounts": {}}


def log(msg):
    print(f"[{datetime.datetime.utcnow():%H:%M:%S}] {msg}", flush=True)


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- tokens
def _app():
    return ((os.environ.get("PINTEREST_APP_ID") or "").strip(),
            (os.environ.get("PINTEREST_APP_SECRET") or "").strip())


def _fernet():
    from cryptography.fernet import Fernet
    secret = _app()[1]
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("pin:" + secret).encode()).digest()))


def enabled(acct):
    app_id, secret = _app()
    return bool(app_id and secret and (os.environ.get(f"PINTEREST_{acct.upper()}_REFRESH_TOKEN") or "").strip())


def access_token(acct):
    """Refresh token -> access token. Naya refresh token encrypted save (dry run mein bhi -
    purana token Pinterest ke paas bekaar ho sakta hai)."""
    app_id, secret = _app()
    env_rt = (os.environ.get(f"PINTEREST_{acct.upper()}_REFRESH_TOKEN") or "").strip()
    env_hash = hashlib.sha256(env_rt.encode()).hexdigest()[:16]
    tokens = _load(TOKENS_FILE, {})
    saved = tokens.get(acct) or {}
    rt = env_rt
    if saved.get("env") == env_hash and saved.get("rt"):
        try:
            rt = _fernet().decrypt(saved["rt"].encode()).decode()
        except Exception as e:
            log(f"{acct}: saved token decrypt fail ({e}) - secret wala use")
    basic = base64.b64encode(f"{app_id}:{secret}".encode()).decode()
    r = requests.post(f"{API}/oauth/token", timeout=60,
                      headers={"Authorization": f"Basic {basic}"},
                      data={"grant_type": "refresh_token", "refresh_token": rt})
    j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if "access_token" not in j:
        raise RuntimeError(f"Pinterest login fail ({r.status_code}): {r.text[:300]}")
    new_rt = j.get("refresh_token")
    if new_rt and new_rt != rt:
        tokens[acct] = {"env": env_hash, "rt": _fernet().encrypt(new_rt.encode()).decode(),
                        "saved": datetime.datetime.utcnow().strftime("%Y-%m-%d")}
        _save(TOKENS_FILE, tokens)
        log(f"{acct}: naya refresh token save ho gaya")
    return j["access_token"]


def _api(method, path, token, **kw):
    r = requests.request(method, f"{API}{path}", timeout=90,
                         headers={"Authorization": f"Bearer {token}"}, **kw)
    if r.status_code >= 300:
        raise RuntimeError(f"Pinterest {method} {path} {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else {}


def boards(token):
    out, bookmark = {}, None
    for _ in range(10):
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        j = _api("GET", "/boards", token, params=params)
        for b in j.get("items", []):
            out[b["name"].strip().lower()] = b["id"]
        bookmark = j.get("bookmark")
        if not bookmark:
            break
    return out


def board_id(token, cache, name, desc):
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    if DRY_RUN:
        return "(new board)"
    b = _api("POST", "/boards", token, json={"name": name[:50], "description": desc[:500],
                                              "privacy": "PUBLIC"})
    cache[key] = b["id"]
    log(f"Naya board: {name}")
    return b["id"]


# ---------------------------------------------------------------- videos
def candidates(acct, done):
    """Pin hone wali videos: nayi pehle, phir purani. (entry, yt_id, short)"""
    cfg = ACCOUNTS[acct]
    now = datetime.datetime.utcnow()
    items = []
    for path, key, short in cfg["sources"]:
        for e in _load(path, []):
            vid = e.get(key)
            if not vid or vid in done:
                continue
            if cfg.get("only_en") and e.get("lang", "en") != "en":
                continue
            try:
                when = datetime.datetime.strptime(e.get("date", ""), "%Y-%m-%d %H:%M")
            except Exception:
                when = now - datetime.timedelta(days=365)
            if now - when < datetime.timedelta(hours=MIN_AGE_HOURS):
                continue
            items.append((when, e, vid, short))
    items.sort(key=lambda x: x[0], reverse=True)
    recent = [i for i in items if now - i[0] <= datetime.timedelta(days=3)]
    older = [i for i in items if now - i[0] > datetime.timedelta(days=3)]
    older.sort(key=lambda x: x[0])        # purani backlog: sab se purani pehle
    seen, out = set(), []
    for _, e, vid, short in recent + older:
        if vid not in seen:
            seen.add(vid)
            out.append((e, vid, short))
    return out


def thumbnail(vid):
    for q in ("maxresdefault", "sddefault", "hqdefault"):
        r = requests.get(f"https://i.ytimg.com/vi/{vid}/{q}.jpg", timeout=30)
        if r.status_code == 200 and len(r.content) > 5000:
            return Image.open(io.BytesIO(r.content)).convert("RGB")
    raise RuntimeError(f"thumbnail nahi mila: {vid}")


def make_pin_image(vid, title, label):
    """1000x1500 (2:3 - Pinterest ka best size): blur background, beech mein thumbnail, neeche title."""
    W, H = 1000, 1500
    th = thumbnail(vid)
    bg = th.copy()
    s = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1)).crop((0, 0, W, H))
    bg = bg.filter(ImageFilter.GaussianBlur(28))
    bg = Image.eval(bg, lambda p: int(p * 0.45))
    tw = W - 60
    t = th.resize((tw, int(th.height * tw / th.width)))
    y0 = 330
    bg.paste(t, (30, y0))
    d = ImageDraw.Draw(bg)
    try:
        f_title = ImageFont.truetype(FONT, 64)
        f_small = ImageFont.truetype(FONT, 38)
    except Exception:
        f_title = f_small = ImageFont.load_default()
    # upar label (channel ka naam)
    d.text((W // 2, 150), label.upper(), font=f_small, fill=(255, 214, 90), anchor="mm")
    d.text((W // 2, 215), "WATCH ON YOUTUBE", font=f_small, fill=(255, 255, 255), anchor="mm")
    # neeche title
    lines = textwrap.wrap(title, 24)[:4]
    y = y0 + t.height + 70
    for ln in lines:
        d.text((W // 2, y), ln, font=f_title, fill=(255, 255, 255), anchor="mm",
               stroke_width=3, stroke_fill=(0, 0, 0))
        y += 82
    buf = io.BytesIO()
    bg.save(buf, "JPEG", quality=88)
    return buf.getvalue()


_client = None


def pin_text(acct, title, entry):
    """Pinterest search ke liye title + description (Gemini; fail ho to simple)."""
    cfg = ACCOUNTS[acct]
    fallback = {"title": title[:100],
                "description": f"{title}. Watch the full video on YouTube - {cfg['name']}."}
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return fallback
    global _client
    try:
        from google import genai
        from google.genai import types
        if _client is None:
            _client = genai.Client(api_key=key)
        extra = entry.get("summary") or entry.get("theme") or entry.get("subject") or ""
        prompt = f"""Write a Pinterest pin for a YouTube video from "{cfg['name']}" ({cfg['about']}).
Video title: {title}
About: {str(extra)[:600]}
Return JSON: {{"title": "pin title, max 90 characters, uses words people search on Pinterest",
 "description": "2-3 natural sentences (max 450 characters) with search keywords, honest about what
 the video shows, ending with an invitation to watch the full video on YouTube. No hashtags spam
 (max 3 hashtags)."}}
Rules: English, no clickbait lies, no politics."""
        for model in MODEL_CANDIDATES:
            try:
                res = _client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json",
                                                       temperature=0.7))
                d = json.loads(res.text)
                if d.get("title") and d.get("description"):
                    return {"title": d["title"][:100], "description": d["description"][:500]}
            except Exception as e:
                log(f"gemini {model}: {str(e)[:150]}")
    except Exception as e:
        log(f"gemini fail: {e}")
    return fallback


# ---------------------------------------------------------------- run
def run_account(acct, state):
    cfg = ACCOUNTS[acct]
    done = state.setdefault(acct, [])
    todo = candidates(acct, set(done))[:PINS_PER_RUN]
    rep = {"pending": len(candidates(acct, set(done))), "pins": []}
    if not todo:
        return rep
    token = access_token(acct)
    cache = boards(token)
    for entry, vid, short in todo:
        title = entry.get("title") or cfg["name"]
        link = f"https://www.youtube.com/shorts/{vid}" if short else f"https://www.youtube.com/watch?v={vid}"
        bname = cfg["board"](entry)
        txt = pin_text(acct, title, entry)
        img = make_pin_image(vid, title, cfg["name"])
        info = {"yt": vid, "board": bname, "title": txt["title"]}
        if DRY_RUN:
            info["dry_run"] = True
            rep["pins"].append(info)
            continue
        bid = board_id(token, cache, bname, cfg["board_desc"])
        pin = _api("POST", "/pins", token, json={
            "board_id": bid, "title": txt["title"], "description": txt["description"],
            "link": link, "alt_text": title[:500],
            "media_source": {"source_type": "image_base64", "content_type": "image/jpeg",
                             "data": base64.b64encode(img).decode()}})
        info["pin_id"] = pin.get("id")
        rep["pins"].append(info)
        done.append(vid)
        log(f"{acct}: pinned {vid} -> {bname}")
        time.sleep(5)
    return rep


def main():
    state = _load(STATE_FILE, {})
    any_enabled = False
    for acct in ACCOUNTS:
        if not enabled(acct):
            REPORT["accounts"][acct] = "skip: token nahi (docs/pinterest.html se connect karein)"
            continue
        any_enabled = True
        try:
            REPORT["accounts"][acct] = run_account(acct, state)
        except Exception as e:
            log(f"{acct} ERROR: {e}")
            REPORT["accounts"][acct] = {"error": str(e)[:400]}
    if not DRY_RUN:
        for k in state:
            state[k] = state[k][-3000:]
        _save(STATE_FILE, state)
    _save(REPORT_FILE, REPORT)
    log(json.dumps(REPORT, ensure_ascii=False)[:1500])
    if not any_enabled:
        log("Koi Pinterest account connect nahi - kuch nahi kiya")


if __name__ == "__main__":
    main()
