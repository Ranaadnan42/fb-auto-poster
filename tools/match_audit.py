"""
Manager ki jaanch: AWAZ aur VIDEO match (din mein 2 dafa, ai_employee.yml ke andar).
Agents banate waqt khud bhi footage check karte hain - ye manager ki DOOSRI, alag jaanch hai, post hone ke BAAD:
  1. Har page ki pichhle ~26 ghante ki sab se nayi video Facebook se uthao
  2. Awaz ko likhai mein badlo (Groq Whisper, waqt ke saath)
  3. Har jumle ke waqt ki tasveer nikaal kar vision AI se poochho: jo bola ja raha hai, wohi dikh raha hai?
  4. Natija match_audit.json mein. Jahan galat tha (bola X, dikhaya Y) wo us page ke agent ko sabaq ban kar
     agli video ke prompt mein jata hai (content_rules.winners) - agent dobara wohi ghalti nahi karta.
Post kabhi delete nahi hoti. Koi message Adnan ko nahi (report mein sirf % dikhta hai).
"""
import os
import sys
import json
import subprocess
import tempfile
import datetime as dt

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
import groq_vision   # noqa: E402

GRAPH = "https://graph.facebook.com/v23.0"
OUT = os.path.join(ROOT, "match_audit.json")
NOW = dt.datetime.now(dt.timezone.utc)
# page -> (id secret, token secret)
PAGES = {
    "islamic": ("FB_PAGE_ID", "FB_PAGE_TOKEN"), "funny": ("FUNNY_PAGE_ID", "FUNNY_PAGE_TOKEN"),
    "frames": ("FRAMES_PAGE_ID", "FRAMES_PAGE_TOKEN"), "scenic": ("SCENIC_PAGE_ID", "SCENIC_PAGE_TOKEN"),
    "war": ("WAR_PAGE_ID", "WAR_PAGE_TOKEN"), "birds": ("BIRDS_PAGE_ID", "BIRDS_PAGE_TOKEN"),
    "pets": ("PETS_PAGE_ID", "PETS_PAGE_TOKEN"), "wild": ("WILD_PAGE_ID", "WILD_PAGE_TOKEN"),
    "news": ("NEWS_PAGE_ID", "NEWS_PAGE_TOKEN"), "newsur": ("NEWSUR_PAGE_ID", "NEWSUR_PAGE_TOKEN"),
    "sports": ("SPORTS_PAGE_ID", "SPORTS_PAGE_TOKEN"),
}
CHECKS = 5          # har video mein kitne jumle check
# Groq ka roz ka quota agents khatam kar dete hain - is liye har page ki APNI Gemini key se pehle dekho
GEMINI_KEYS = {"islamic": "GEMINI_KEY_ISLAMIC", "funny": "GEMINI_KEY_FUNNY", "frames": "GEMINI_KEY_FRAMES",
               "scenic": "SCENIC_GEMINI_API_KEY", "war": "WAR_GEMINI_API_KEY", "birds": "BIRDS_GEMINI_API_KEY",
               "pets": "PETS_GEMINI_API_KEY", "wild": "WILD_GEMINI_API_KEY", "news": "NEWS_GEMINI_API_KEY",
               "newsur": "NEWSUR_GEMINI_API_KEY", "sports": "SPORTS_GEMINI_API_KEY"}
GEMINI_MODELS = ["gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-flash-latest"]


def gemini_vision(img, prompt, key):
    import base64
    import re
    if not key:
        return None
    b = base64.b64encode(img).decode()
    for m in GEMINI_MODELS:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}",
                              timeout=40, json={"contents": [{"parts": [{"text": prompt}, {"inline_data": {
                                  "mime_type": "image/jpeg", "data": b}}]}], "generationConfig": {"temperature": 0}})
            if r.status_code != 200:
                continue
            t = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(re.search(r"\{.*\}", t, re.S).group(0))
        except Exception:
            continue
    return None


def _ffmpeg():
    import shutil
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "imageio-ffmpeg"], timeout=180)
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()


FF = None


def env(k):
    return (os.environ.get(k) or "").strip()


def latest_video(pid, token):
    j = requests.get(f"{GRAPH}/{pid}/videos", timeout=60, params={
        "access_token": token, "fields": "id,source,created_time,description,length", "limit": 5}).json()
    if "error" in j:
        raise RuntimeError(j["error"].get("message", "")[:150])
    for v in j.get("data", []):
        t = dt.datetime.strptime(v["created_time"], "%Y-%m-%dT%H:%M:%S%z")
        if (NOW - t).total_seconds() < 26 * 3600 and v.get("source"):
            return v
    return None


def transcribe(mp4, tmp):
    mp3 = os.path.join(tmp, "a.mp3")
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000",
                    "-b:a", "48k", mp3], check=True, timeout=180)
    key = env("GROQ_API_KEY")
    for model in ("whisper-large-v3-turbo", "whisper-large-v3"):
        with open(mp3, "rb") as f:
            r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", timeout=180,
                              headers={"Authorization": f"Bearer {key}"},
                              files={"file": ("a.mp3", f, "audio/mpeg")},
                              data={"model": model, "response_format": "verbose_json"})
        if r.status_code == 200:
            return [s for s in r.json().get("segments", []) if len((s.get("text") or "").strip()) > 8]
        print("   whisper", model, r.status_code, r.text[:120], flush=True)
    return []


def frame(mp4, sec, tmp):
    jpg = os.path.join(tmp, f"f{int(sec * 10)}.jpg")
    subprocess.run([FF, "-y", "-loglevel", "error", "-ss", f"{sec:.2f}", "-i", mp4, "-frames:v", "1",
                    "-vf", "scale=512:-2", jpg], check=True, timeout=60)
    return open(jpg, "rb").read()


def audit(pid, token, name=""):
    v = latest_video(pid, token)
    if not v:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        mp4 = os.path.join(tmp, "v.mp4")
        with requests.get(v["source"], stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(mp4, "wb") as f:
                for ch in r.iter_content(1 << 20):
                    f.write(ch)
        segs = transcribe(mp4, tmp)
        if not segs:
            return {"video": v["id"], "at": v["created_time"], "note": "awaz/likhai nahi mili (shayad sirf music)"}
        step = max(1, len(segs) // CHECKS)
        pick = segs[::step][:CHECKS]
        res = []
        for s in pick:
            said = s["text"].strip()[:220]
            mid = (float(s["start"]) + float(s["end"])) / 2
            try:
                img = frame(mp4, mid, tmp)
            except Exception:
                continue
            q = f"""The narrator of this video says at this exact moment (may be Urdu/Hindi/English):
"{said}"
Look at the video frame. Does the picture show the specific thing being talked about (same subject, place, animal,
person type, object or action)? A loosely related or generic clip is NOT a match. Funny/comedy acting scenes match
if the situation fits the words.
Reply JSON: {{"match": true/false, "said_subject": "<what the words are about, in English, max 8 words>",
"shown": "<what the picture actually shows, max 8 words>"}}"""
            ans = gemini_vision(img, q, env(GEMINI_KEYS.get(name, ""))) or groq_vision.ask_json([img], q)
            if isinstance(ans, dict) and "match" in ans:
                res.append({"t": round(mid, 1), "match": bool(ans.get("match")),
                            "said": str(ans.get("said_subject", ""))[:80], "shown": str(ans.get("shown", ""))[:80]})
        if not res:
            return {"video": v["id"], "at": v["created_time"], "note": "vision AI busy - agli dafa"}
        ok = sum(1 for x in res if x["match"])
        return {"video": v["id"], "at": v["created_time"], "title": (v.get("description") or "")[:80],
                "score": round(100 * ok / len(res)), "checked": len(res),
                "misses": [x for x in res if not x["match"]]}


def main():
    global FF
    FF = _ffmpeg()
    try:
        rec = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        rec = {}
    if not env("GROQ_API_KEY"):
        print("GROQ_API_KEY nahi - jaanch nahi ho sakti")
        return
    for name, (ik, tk) in PAGES.items():
        pid, token = env(ik), env(tk)
        if not (pid and token):
            continue
        prev = rec.get(name, {})
        try:
            r = audit(pid, token, name)
        except Exception as e:
            print(f"== {name}: fail {str(e)[:150]}", flush=True)
            continue
        if r and str(r.get("note", "")).startswith("vision AI busy"):
            print(f"== {name}: vision AI busy - ye video agli dafa dobara check hogi", flush=True)
            continue                      # video ko 'ho gayi' mark nahi karte, warna kabhi check na hoti
        if not r or r.get("video") == prev.get("video"):
            print(f"== {name}: nayi video nahi", flush=True)
            continue
        hist = (prev.get("history") or [])[-29:]
        if "score" in r:
            hist.append({"day": NOW.date().isoformat(), "score": r["score"]})
        r["history"] = hist
        r["avg"] = round(sum(h["score"] for h in hist) / len(hist)) if hist else None
        # purani ghaltiyan bhi yaad rakho (agent ke sabaq ke liye), aakhri 8
        r["lessons"] = ((prev.get("lessons") or []) + [f'said "{m["said"]}" but showed "{m["shown"]}"'
                                                         for m in r.get("misses", [])])[-8:]
        rec[name] = r
        print(f"== {name}: {r.get('score', r.get('note'))}% | misses {r.get('misses')}", flush=True)
    json.dump(rec, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
