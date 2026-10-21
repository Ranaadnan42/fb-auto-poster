"""
Growth Bot - sirf APNE pages/channels par kaam karta hai (spam nahi, ban ka khatra nahi):
  1. Apni videos/posts par logon ke comments ka khud achha jawab (Gemini) -> engagement barhti hai,
     algorithm video zyada naye logon ko dikhata hai.
  2. Har nayi video/post par channel/page ka apna pehla comment (sawal + subscribe/follow ki dawat).

Accounts (jis ka secret na ho woh chup chaap skip):
  YouTube : islamic, funny, legends (YT_REFRESH_TOKEN), movie, world, frames
  Facebook: islamic (FB_PAGE_*), funny (FUNNY_PAGE_*), legends (CINE_FB_*)
Yaad rakha jata hai: growth_state.json (kis comment ka jawab diya, kis video par comment kiya)
"""
import os
import re
import json
import time
import datetime as dt

import requests

STATE_FILE = "growth_state.json"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_CANDIDATES = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]
GRAPH = "https://graph.facebook.com/v23.0"
YT = "https://www.googleapis.com/youtube/v3"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MAX_REPLIES = int(os.environ.get("MAX_REPLIES") or 15)   # har account par har run (YouTube quota bachane ke liye)
MAX_AGE_DAYS = 7          # is se purane comments ka jawab nahi
NEW_VIDEO_DAYS = 3        # itne din ki nayi videos par apna pehla comment

PERSONA = {
    "islamic": ("Islamic Motivational Videos",
                "respectful Islamic motivational channel. Use 'JazakAllah', 'Ameen', 'MashaAllah' naturally. "
                "Never give fatwas or rulings; for religious questions advise asking a qualified scholar."),
    "funny": ("Hansi Ka Adda", "light-hearted Pakistani comedy page, friendly and witty, clean humour only."),
    "legends": ("Legends Untold", "epic fantasy story channel, storyteller voice, hint at upcoming stories."),
    "movie": ("Plot Twist Recaps", "movie recap channel, friendly film fan, no spoilers of other films."),
    "world": ("World documentary channel", "curious, warm travel-documentary host."),
    "frames": ("Frames of Life", "curious, warm documentary host."),
}

YT_ACCOUNTS = {
    "islamic": ("YT_ISLAMIC_CLIENT_ID", "YT_ISLAMIC_CLIENT_SECRET", "YT_ISLAMIC_REFRESH_TOKEN"),
    "funny": ("YT_FUNNY_CLIENT_ID", "YT_FUNNY_CLIENT_SECRET", "YT_FUNNY_REFRESH_TOKEN"),
    "legends": ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"),
    "movie": ("YT_MOVIE_CLIENT_ID", "YT_MOVIE_CLIENT_SECRET", "YT_MOVIE_REFRESH_TOKEN"),
    "world": ("YT_WORLD_CLIENT_ID", "YT_WORLD_CLIENT_SECRET", "YT_WORLD_REFRESH_TOKEN"),
    "frames": ("YT_FRAMES_CLIENT_ID", "YT_FRAMES_CLIENT_SECRET", "YT_FRAMES_REFRESH_TOKEN"),
}
FB_ACCOUNTS = {
    "islamic": ("FB_PAGE_ID", "FB_PAGE_TOKEN"),
    "funny": ("FUNNY_PAGE_ID", "FUNNY_PAGE_TOKEN"),
    "legends": ("CINE_FB_PAGE_ID", "CINE_FB_TOKEN"),
}

report = []


def log(msg):
    print(msg, flush=True)


def env(k):
    return (os.environ.get(k) or "").strip()


# ------------------------------------------------------------------ state
def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    for k, v in st.items():
        if isinstance(v, list):
            st[k] = v[-3000:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def recent(ts, days):
    try:
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+0000", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - t).days < days
    except Exception:
        return True


# ------------------------------------------------------------------ Gemini
_client = None


def ask_json(prompt):
    global _client
    from google import genai
    from google.genai import types
    if _client is None:
        _client = genai.Client(api_key=GEMINI_KEY)
    last = None
    for model in MODEL_CANDIDATES:
        for attempt in range(2):
            try:
                res = _client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.8))
                return json.loads(res.text)
            except Exception as e:
                last = e
                log(f"{model} try {attempt + 1} failed: {str(e)[:150]}")
                time.sleep(4)
    raise RuntimeError(f"Gemini fail: {last}")


def write_replies(acct, platform, items):
    """items: [{"video": title, "comment": text}] -> list of reply strings ('' = skip)."""
    if not items:
        return []
    name, style = PERSONA[acct]
    follow = "subscribe" if platform == "youtube" else "follow the page"
    data = ask_json(f"""You reply to viewer comments as the owner of the {platform} {('channel' if platform == 'youtube' else 'page')} "{name}".
Style: {style}
Rules:
- Reply in the SAME language and script the commenter used (Urdu script, Roman Urdu, English, Arabic, Hindi...).
- Short and human: 1-2 sentences, max 25 words. Thank them, respond to what they actually said.
- About 1 in 4 replies may end with a natural invite to {follow} for daily videos - not every time.
- Sometimes ask a small friendly question back to keep the conversation going.
- No links, no hashtags, no copy-paste sameness between replies.
- If the comment is spam, abusive, a link/promotion, or just meaningless, return "" for it.
Comments (index, video title, comment):
{json.dumps([[i, it['video'], it['comment'][:400]] for i, it in enumerate(items)], ensure_ascii=False)}
Return JSON: {{"replies": [{{"i": 0, "reply": "..."}}, ...]}} with one entry per comment.""")
    out = [""] * len(items)
    for r in data.get("replies", []):
        try:
            out[int(r["i"])] = (r.get("reply") or "").strip()[:500]
        except Exception:
            pass
    return out


def first_comment(acct, platform, title):
    name, style = PERSONA[acct]
    follow = "Subscribe" if platform == "youtube" else "Follow"
    data = ask_json(f"""You own the {platform} channel/page "{name}" ({style}).
Write the FIRST comment you post under your own new video titled: "{title}".
Use the same language/script as the title. 1-2 short sentences: ask viewers one engaging question about the video
so they reply, then a short invite: "{follow}" for a new video every day. No links, max 2 emojis.
Return JSON: {{"comment": "..."}}""")
    return (data.get("comment") or "").strip()[:500]


# ------------------------------------------------------------------ YouTube
def yt_token(acct):
    cid, sec, ref = (env(k) for k in YT_ACCOUNTS[acct])
    if not (cid and sec and ref):
        return None
    j = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "client_id": cid, "client_secret": sec, "refresh_token": ref, "grant_type": "refresh_token"}).json()
    if "access_token" not in j:
        raise RuntimeError(f"login fail: {j}")
    tok = j["access_token"]
    scope = requests.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": tok}, timeout=30).json().get("scope", "")
    if "youtube.force-ssl" not in scope and not re.search(r"auth/youtube(\s|$)", scope):
        raise RuntimeError("is channel ke token mein comment ki ijazat (youtube.force-ssl) nahi - "
                           "naya refresh token banana hoga (sirf upload ki ijazat hai)")
    return tok


def yt_get(tok, path, **params):
    r = requests.get(f"{YT}/{path}", params=params, headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"{path}: {j['error'].get('message')}")
    return j


def yt_post(tok, path, body):
    if DRY_RUN:
        log(f"   [dry] {path}: {json.dumps(body, ensure_ascii=False)[:200]}")
        return True
    r = requests.post(f"{YT}/{path}", params={"part": "snippet"}, json=body,
                      headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    if r.status_code != 200:
        log(f"   YouTube {r.status_code}: {r.text[:200]}")
        return False
    return True


def run_youtube(acct, st):
    tok = yt_token(acct)
    if not tok:
        return
    ch = yt_get(tok, "channels", part="id,contentDetails", mine="true")["items"][0]
    cid = ch["id"]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    replied = set(st.setdefault("yt_replied", []))
    seeded = set(st.setdefault("yt_seeded", []))

    # 1) nayi videos par apna pehla comment
    vids = yt_get(tok, "playlistItems", part="snippet", playlistId=uploads, maxResults=10).get("items", [])
    seeded_now = 0
    for v in vids:
        sn = v["snippet"]
        vid = sn["resourceId"]["videoId"]
        if vid in seeded or not recent(sn["publishedAt"], NEW_VIDEO_DAYS):
            continue
        text = first_comment(acct, "youtube", sn["title"])
        if text and yt_post(tok, "commentThreads", {"snippet": {"videoId": vid, "topLevelComment": {
                "snippet": {"textOriginal": text}}}}):
            st["yt_seeded"].append(vid); seeded_now += 1
            log(f"   pehla comment: {sn['title'][:50]} -> {text[:80]}")

    # 2) logon ke comments ka jawab
    threads = yt_get(tok, "commentThreads", part="snippet", allThreadsRelatedToChannelId=cid,
                     maxResults=100, order="time", textFormat="plainText").get("items", [])
    titles = {v["snippet"]["resourceId"]["videoId"]: v["snippet"]["title"] for v in vids}
    todo = []
    for t in threads:
        top = t["snippet"]["topLevelComment"]
        s = top["snippet"]
        if top["id"] in replied or t["snippet"].get("totalReplyCount", 0) > 0:
            continue
        if (s.get("authorChannelId") or {}).get("value") == cid or not recent(s["publishedAt"], MAX_AGE_DAYS):
            continue
        todo.append({"id": top["id"], "video": titles.get(t["snippet"].get("videoId"), ""),
                     "comment": s.get("textOriginal") or s.get("textDisplay") or ""})
        if len(todo) >= MAX_REPLIES:
            break
    done = 0
    for it, reply in zip(todo, write_replies(acct, "youtube", todo)):
        st["yt_replied"].append(it["id"])
        if reply and yt_post(tok, "comments", {"snippet": {"parentId": it["id"], "textOriginal": reply}}):
            done += 1
            log(f"   jawab: {it['comment'][:50]!r} -> {reply[:80]}")
    report.append(f"YouTube {acct}: {done} jawab, {seeded_now} nayi video par comment")


# ------------------------------------------------------------------ Facebook
def fb_call(method, path, token, **params):
    params["access_token"] = token
    r = requests.request(method, f"{GRAPH}/{path}", params=params if method == "GET" else None,
                         data=params if method != "GET" else None, timeout=60)
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"].get("message", j["error"]))
    return j


def fb_comment(token, obj_id, text):
    if DRY_RUN:
        log(f"   [dry] FB {obj_id}: {text[:120]}")
        return True
    try:
        fb_call("POST", f"{obj_id}/comments", token, message=text)
        return True
    except Exception as e:
        log(f"   FB comment fail: {str(e)[:200]}")
        return False


def run_facebook(acct, st):
    pid, token = (env(k) for k in FB_ACCOUNTS[acct])
    if not (pid and token):
        return
    replied = set(st.setdefault("fb_replied", []))
    seeded = set(st.setdefault("fb_seeded", []))
    posts = fb_call("GET", f"{pid}/feed", token, limit=15,
                    fields="id,message,created_time,comments.limit(50).order(reverse_chronological)"
                           "{id,from,message,created_time,comment_count}").get("data", [])
    seeded_now, todo = 0, []
    for p in posts:
        title = (p.get("message") or "").split("\n")[0][:120]
        if p["id"] not in seeded and recent(p["created_time"], NEW_VIDEO_DAYS) and title:
            text = first_comment(acct, "facebook", title)
            if text and fb_comment(token, p["id"], text):
                st["fb_seeded"].append(p["id"]); seeded_now += 1
                log(f"   pehla comment: {title[:50]} -> {text[:80]}")
        for c in (p.get("comments") or {}).get("data", []):
            if c["id"] in replied or c.get("comment_count", 0) > 0:
                continue
            if (c.get("from") or {}).get("id") == pid or not recent(c["created_time"], MAX_AGE_DAYS):
                continue
            if len(todo) < MAX_REPLIES and c.get("message"):
                todo.append({"id": c["id"], "video": title, "comment": c["message"]})
    done = 0
    for it, reply in zip(todo, write_replies(acct, "facebook", todo)):
        st["fb_replied"].append(it["id"])
        if reply and fb_comment(token, it["id"], reply):
            done += 1
            log(f"   jawab: {it['comment'][:50]!r} -> {reply[:80]}")
    report.append(f"Facebook {acct}: {done} jawab, {seeded_now} nayi post par comment")


# ------------------------------------------------------------------ main
def main():
    st = load_state()
    for acct in YT_ACCOUNTS:
        log(f"== YouTube {acct}")
        try:
            run_youtube(acct, st)
        except Exception as e:
            report.append(f"YouTube {acct}: skip - {str(e)[:200]}")
        save_state(st)
    for acct in FB_ACCOUNTS:
        log(f"== Facebook {acct}")
        try:
            run_facebook(acct, st)
        except Exception as e:
            report.append(f"Facebook {acct}: skip - {str(e)[:200]}")
        save_state(st)
    log("\n===== Growth Bot report =====")
    for line in report:
        log(line)
    with open("growth_last_run.json", "w", encoding="utf-8") as f:
        json.dump({"at": dt.datetime.utcnow().isoformat() + "Z", "report": report}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
