"""
Laughter (hansi) sound effects.
Wikimedia Commons se sirf Public Domain / CC0 hansi ki awaazein download hoti hain
(sfx/laughs/ mein save, credits sfx/laughs/CREDITS.json mein), phir videos mein punchline
ke baad mila di jati hain.
"""
import os
import json
import random
import subprocess

import requests

DIR = os.path.join("sfx", "laughs")
CREDITS = os.path.join(DIR, "CREDITS.json")
UA = {"User-Agent": "HansiKaAddaBot/1.0 (ranaadnan320@gmail.com)"}
SEARCHES = ["audience laughter", "crowd laughing", "laugh track", "people laughing",
            "laughter", "laughing", "group laughing", "studio audience laugh", "giggle",
            "chuckle", "laughing man", "laughing woman", "children laughing", "laugh sound",
            "funny laugh", "sitcom laughter"]
FREE = ("public domain", "cc0", "pd")
HANSI_WORDS = ("ہنس", "ہاہا", "قہقہ", "ہی ہی", "کھلکھلا")


def log(m):
    print(f"[sfx] {m}", flush=True)


def _run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0


def ensure_laughs(min_count=6):
    os.makedirs(DIR, exist_ok=True)
    have = [f for f in os.listdir(DIR) if f.endswith(".mp3")]
    if len(have) >= min_count:
        return have
    try:
        credits = json.load(open(CREDITS, encoding="utf-8"))
    except Exception:
        credits = {}
    seen = set(credits.values()) if credits else set()
    for q in SEARCHES:
        if len(have) >= 12:
            break
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=40, params={
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": f"{q} filetype:audio", "gsrnamespace": 6, "gsrlimit": 40,
                "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime"})
            pages = (r.json().get("query") or {}).get("pages", {}).values()
        except Exception as e:
            log(f"search fail {q}: {e}")
            continue
        for p in pages:
            if len(have) >= 12:
                break
            ii = (p.get("imageinfo") or [{}])[0]
            title = p.get("title", "")
            lic = ((ii.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "").lower()
            dur = float(ii.get("duration") or 0)
            low = title.lower()
            if (not any(k in lic for k in FREE)
                    or not any(k in low for k in ("laugh", "giggl", "chuckl"))
                    or any(b in low for b in ("evil", "witch", "horror", "scary", "maniac"))
                    or not (1.0 <= dur <= 40) or title in seen):
                continue
            src = os.path.join(DIR, "tmp_src")
            name = f"laugh_{len(have) + 1:02d}.mp3"
            try:
                with requests.get(ii["url"], headers=UA, timeout=120) as resp:
                    resp.raise_for_status()
                    open(src, "wb").write(resp.content)
                # 4 second tak, shuru ki khamoshi hata kar, normalize
                ok = _run(["ffmpeg", "-y", "-i", src, "-af",
                           "silenceremove=start_periods=1:start_threshold=-40dB,"
                           "atrim=0:4,afade=t=out:st=3:d=1,loudnorm=I=-18:TP=-2",
                           "-ar", "44100", "-ac", "2", "-b:a", "128k", os.path.join(DIR, name)])
                if ok:
                    have.append(name)
                    credits[name] = title
                    seen.add(title)
                    log(f"added {name} <- {title} ({lic})")
            except Exception as e:
                log(f"download fail {title}: {e}")
            finally:
                if os.path.exists(src):
                    os.remove(src)
    json.dump(credits, open(CREDITS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return have


def is_funny_text(text):
    return any(w in (text or "") for w in HANSI_WORDS)


def add_laughs(video, times, volume=0.55):
    """`times` (seconds) par hansi mila deta hai. Video file ko in-place badalta hai."""
    times = sorted(t for t in times if t is not None and t >= 0)
    if not times:
        return 0
    files = ensure_laughs()
    if not files:
        log("koi laugh file nahi mili, skip")
        return 0
    random.shuffle(files)
    inputs, chains = [], []
    for i, t in enumerate(times):
        f = os.path.join(DIR, files[i % len(files)])
        inputs += ["-i", f]
        ms = int(t * 1000)
        chains.append(f"[{i + 1}:a]volume={volume},adelay={ms}|{ms}[l{i}]")
    mix = "[0:a]" + "".join(f"[l{i}]" for i in range(len(times)))
    chains.append(f"{mix}amix=inputs={len(times) + 1}:duration=first:normalize=0[a]")
    out = video + ".laugh.mp4"
    ok = _run(["ffmpeg", "-y", "-i", video] + inputs + [
        "-filter_complex", ";".join(chains), "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    if ok:
        os.replace(out, video)
        log(f"{len(times)} laughs added")
        return len(times)
    log("laugh mix fail, video bina hansi ke")
    return 0
