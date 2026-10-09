"""
Laughter (hansi) sound effects.
Wikimedia Commons se free-license hansi ki awaazein (Public Domain, CC0, CC BY, CC BY-SA)
download hoti hain, sfx/laughs/ mein save hoti hain, aur punchline ke baad video mein mila di
jati hain. CC BY / BY-SA awaaz use ho to post ki description mein credit line lag jati hai.
"""
import os
import re
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
            "funny laugh", "sitcom laughter", "baby laughing"]
NO_CREDIT = ("public domain", "cc0", "pd")
WITH_CREDIT = ()                         # sirf bina-credit (PD/CC0) awaazein, caption saaf rahe
HANSI_WORDS = ("ہنس", "ہاہا", "قہقہ", "ہی ہی", "کھلکھلا")
USED = set()                              # is run mein use hui files


def log(m):
    print(f"[sfx] {m}", flush=True)


def _run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0


def _load():
    try:
        data = json.load(open(CREDITS, encoding="utf-8"))
    except Exception:
        return {}
    return {k: (v if isinstance(v, dict) else {"title": v, "license": "", "artist": ""})
            for k, v in data.items()}


def _clean_old(credits):
    """Purani galat files hatao (Lingua Libre = bolay hue alfaaz, hansi nahi)."""
    for name, c in list(credits.items()):
        if "LL-Q" in c.get("title", ""):
            try:
                os.remove(os.path.join(DIR, name))
            except FileNotFoundError:
                pass
            credits.pop(name)
            log(f"removed {name} ({c['title']})")


def ensure_laughs(min_count=8):
    os.makedirs(DIR, exist_ok=True)
    credits = _load()
    _clean_old(credits)
    for f in os.listdir(DIR):                     # bina credit wali files hatao
        if f.endswith(".mp3") and f not in credits and not f.startswith("crowd_"):
            os.remove(os.path.join(DIR, f))
    have = [f for f in os.listdir(DIR) if f.endswith(".mp3") and f in credits]
    if len(have) >= 1 and os.environ.get("SFX_NO_SEARCH"):
        return have
    if len(have) >= min_count:
        return have
    seen = {c["title"] for c in credits.values()}
    for q in SEARCHES:
        if len(have) >= 14:
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
            if len(have) >= 14:
                break
            ii = (p.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata") or {}
            title = p.get("title", "")
            lic = (meta.get("LicenseShortName") or {}).get("value", "")
            licl = lic.lower()
            dur = float(ii.get("duration") or 0)
            low = title.lower()
            if (not any(k in licl for k in NO_CREDIT)
                    or "nc" in licl or "nd" in licl
                    or not any(k in low for k in ("laugh", "giggl", "chuckl"))
                    or "ll-q" in low
                    or re.search(r"song|music|dj |^file:[a-z]{2,3}(-[a-z]{2,4})?-", low)
                    or any(b in low for b in ("evil", "witch", "horror", "scary", "maniac", "crying",
                                            "beast", "krusty", "impression", "kookaburra", "bird"))
                    or not (1.0 <= dur <= 60) or title in seen):
                continue
            artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
            src = os.path.join(DIR, "tmp_src")
            name = f"laugh_{len(credits) + 1:02d}.mp3"
            while os.path.exists(os.path.join(DIR, name)):
                name = f"laugh_{random.randint(10, 999):03d}.mp3"
            try:
                with requests.get(ii["url"], headers=UA, timeout=120) as resp:
                    resp.raise_for_status()
                    open(src, "wb").write(resp.content)
                ok = _run(["ffmpeg", "-y", "-i", src, "-af",
                           "silenceremove=start_periods=1:start_threshold=-40dB,"
                           "atrim=0:4,afade=t=out:st=3:d=1,loudnorm=I=-18:TP=-2",
                           "-ar", "44100", "-ac", "2", "-b:a", "128k", os.path.join(DIR, name)])
                if ok:
                    have.append(name)
                    credits[name] = {"title": title, "license": lic, "artist": artist[:80]}
                    seen.add(title)
                    log(f"added {name} <- {title} ({lic})")
            except Exception as e:
                log(f"download fail {title}: {e}")
            finally:
                if os.path.exists(src):
                    os.remove(src)
    json.dump(credits, open(CREDITS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return have


def all_laughs():
    base = ensure_laughs()
    crowd = make_variants(base) if base else []
    return base + crowd


def make_variants(sources):
    """PD hansi se mukhtalif 'crowd laughter' variants banata hai (pitch/delay layering)."""
    made = []
    for n in range(1, 7):
        name = f"crowd_{n:02d}.mp3"
        path = os.path.join(DIR, name)
        if os.path.exists(path):
            made.append(name)
            continue
        rnd = random.Random(n)
        layers = 4 + n % 3
        ins, chains = [], []
        for j in range(layers):
            src = os.path.join(DIR, rnd.choice(sources))
            ins += ["-i", src]
            rate = rnd.uniform(0.82, 1.22)
            ms = int(rnd.uniform(0, 900))
            vol = rnd.uniform(0.35, 0.8)
            chains.append(f"[{j}:a]aloop=loop=2:size=200000,asetrate={int(44100 * rate)},aresample=44100,"
                          f"adelay={ms}|{ms},volume={vol:.2f}[x{j}]")
        chains.append("".join(f"[x{j}]" for j in range(layers)) +
                      f"amix=inputs={layers}:normalize=0,atrim=0:3.5,afade=t=in:d=0.1,"
                      f"afade=t=out:st=2.5:d=1,loudnorm=I=-18:TP=-2[a]")
        if _run(["ffmpeg", "-y"] + ins + ["-filter_complex", ";".join(chains), "-map", "[a]",
                                          "-ar", "44100", "-ac", "2", "-b:a", "128k", path]):
            made.append(name)
    return made


def is_funny_text(text):
    return any(w in (text or "") for w in HANSI_WORDS)


def credit_line():
    """CC BY / BY-SA awaazon ke liye attribution (description ke aakhir mein)."""
    credits = _load()
    parts = []
    for f in sorted(USED):
        c = credits.get(f) or {}
        if c and not any(k in c.get("license", "").lower() for k in NO_CREDIT):
            t = c["title"].replace("File:", "")[:45]
            parts.append(f"{t} by {c.get('artist') or 'Wikimedia Commons'} ({c['license']})")
    return ("Laugh sounds: " + "; ".join(parts) + " - via Wikimedia Commons") if parts else ""


def add_laughs(video, times, volume=0.55):
    """`times` (seconds) par hansi mila deta hai. Video file ko in-place badalta hai."""
    times = sorted(t for t in times if t is not None and t >= 0)
    if not times:
        return 0
    files = all_laughs()
    # crowd wali zyada, akeli hansi kam
    files = [f for f in files if f.startswith("crowd_")] * 2 + [f for f in files if not f.startswith("crowd_")]
    if not files:
        log("koi laugh file nahi mili, skip")
        return 0
    random.shuffle(files)
    inputs, chains, used = [], [], []
    for i, t in enumerate(times):
        f = files[i % len(files)]
        used.append(f)
        inputs += ["-i", os.path.join(DIR, f)]
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
        USED.update(used)
        log(f"{len(times)} laughs added")
        return len(times)
    log("laugh mix fail, video bina hansi ke")
    return 0
