"""
Footage dhoondne ki shared jagah (sab bots ke liye).
Pixabay ke ilawa aur platforms (sab free, commercial use theek):
  Videos: Pixabay, Pexels (sirf agar PEXELS_API_KEY ho), Wikimedia Commons, NASA (chaand/taare/zameen/space)
  Photos: Pixabay, Pexels (key ho to), Wikimedia Commons, Openverse (Flickr waghera), NASA
Jab kisi cheez ki video na mile to usi cheez ki ASLI photo ko halka zoom (Ken Burns) de kar clip banti hai -
taake jo bola ja raha hai wahi dikhe, koi be-taalluq clip nahi.
"""
import os
import re
import subprocess

import requests

PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
UA = {"User-Agent": "FbAutoPosterBot/1.0 (https://github.com/Ranaadnan42/fb-auto-poster)"}
_BAD_LIC = ("nc", "nd", "noncommercial", "noderiv")
SPACE = {"moon", "moons", "star", "stars", "sun", "space", "galaxy", "planet", "planets", "earth", "eclipse",
         "comet", "meteor", "universe", "cosmos", "nebula", "orbit", "sky", "night", "crescent", "mars", "saturn"}


def _clean(t):
    return re.sub(r"<[^>]+>", " ", t or "").replace("_", " ").lower()


def _log(msg):
    print(f"[footage] {msg}", flush=True)


# ---------------------------------------------------------------- videos
def pixabay_videos(q, vertical=False):
    if not PIXABAY_KEY:
        return []
    try:
        r = requests.get("https://pixabay.com/api/videos/", timeout=40, params={
            "key": PIXABAY_KEY, "q": q[:90], "safesearch": "true", "per_page": 40})
        out = []
        for h in r.json().get("hits", []):
            v = h.get("videos", {})
            pick = next((v[s] for s in ("large", "medium")
                         if v.get(s, {}).get("url") and v[s].get("width", 0) >= 1280), None)
            if pick and h.get("duration", 0) >= 3:
                out.append({"id": f"px{h['id']}", "url": pick["url"], "text": (h.get("tags") or "").lower(),
                            "dur": h.get("duration", 10), "src": "pixabay",
                            "vertical": pick.get("height", 0) > pick.get("width", 1)})
        return out
    except Exception as e:
        _log(f"Pixabay error ({q}): {str(e)[:100]}")
        return []


def pexels_videos(q, vertical=False):
    if not PEXELS_KEY:
        return []
    try:
        r = requests.get("https://api.pexels.com/videos/search", timeout=40, headers={"Authorization": PEXELS_KEY},
                         params={"query": q[:90], "per_page": 30, "orientation": "portrait" if vertical else "landscape"})
        out = []
        for v in r.json().get("videos", []):
            fs = sorted([f for f in v.get("video_files", []) if f.get("link")
                         and max(f.get("width") or 0, f.get("height") or 0) >= 1280], key=lambda f: f.get("width") or 0)
            if fs and v.get("duration", 0) >= 3:
                out.append({"id": f"pe{v['id']}", "url": fs[0]["link"], "dur": v.get("duration", 10),
                            "text": (v.get("url") or "").lower().replace("-", " "), "src": "pexels",
                            "vertical": vertical})
        return out
    except Exception as e:
        _log(f"Pexels error ({q}): {str(e)[:100]}")
        return []


def commons(q, video=True):
    """Wikimedia Commons: duniya ki asli jagahon, masjidon, khanon, janwaron ki free videos/photos."""
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=40, params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 30,
            "gsrsearch": ("filetype:video " if video else "filetype:bitmap ") + q[:90],
            "prop": "videoinfo" if video else "imageinfo",
            ("viprop" if video else "iiprop"): "url|size|extmetadata" + ("|derivatives" if video else ""),
            **({} if video else {"iiurlwidth": 1920})})
        out = []
        for pg in (r.json().get("query", {}).get("pages", {}) or {}).values():
            info = (pg.get("videoinfo") or pg.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            lic = (meta.get("LicenseShortName", {}).get("value") or "").lower()
            if any(b in lic.replace("-", " ").split() for b in _BAD_LIC):
                continue
            text = _clean(pg.get("title", "")) + " " + _clean(meta.get("ImageDescription", {}).get("value"))[:300]
            if video:
                ders = [d for d in info.get("derivatives", []) if d.get("src") and (d.get("height") or 0) >= 480]
                ders.sort(key=lambda d: abs((d.get("height") or 0) - 1080))
                url = ders[0]["src"] if ders else info.get("url")
                dur = float(info.get("duration") or 10)
                if (info.get("width") or 0) < 640 or not url or dur < 3:
                    continue
                out.append({"id": f"wm{pg.get('pageid')}", "url": url, "text": text, "dur": min(dur, 60),
                            "src": "commons", "vertical": (info.get("height") or 0) > (info.get("width") or 1)})
            else:
                url = info.get("thumburl") or info.get("url")
                if (info.get("width") or 0) < 1000 or not url:
                    continue
                out.append({"id": f"wmi{pg.get('pageid')}", "url": url, "text": text, "photo": True, "src": "commons"})
        return out
    except Exception as e:
        _log(f"Commons error ({q}): {str(e)[:100]}")
        return []


def nasa(q, video=True):
    """NASA ki free (public domain) videos/photos - sirf chaand, taare, suraj, zameen, aasman wali baat par."""
    if not (set(re.findall(r"[a-z]+", q.lower())) & SPACE):
        return []
    try:
        r = requests.get("https://images-api.nasa.gov/search", timeout=40,
                         params={"q": q[:90], "media_type": "video" if video else "image", "page_size": 20})
        out = []
        for it in r.json().get("collection", {}).get("items", [])[:12]:
            d = (it.get("data") or [{}])[0]
            nid = d.get("nasa_id")
            if not nid:
                continue
            text = _clean(f"{d.get('title', '')} {' '.join(d.get('keywords') or [])} {(d.get('description') or '')[:200]}")
            if video:
                try:
                    files = requests.get(it["href"], timeout=30).json()
                except Exception:
                    continue
                mp4 = [f for f in files if isinstance(f, str) and f.endswith(".mp4") and "~orig" not in f]
                pick = next((f for f in mp4 if "~large" in f), None) or next((f for f in mp4 if "~medium" in f), None)
                if pick:
                    out.append({"id": f"na{nid}", "url": pick.replace("http://", "https://"), "text": text,
                                "dur": 15, "src": "nasa", "vertical": False})
            else:
                link = next((l.get("href") for l in it.get("links") or [] if l.get("render") == "image"), None)
                if link:
                    out.append({"id": f"nai{nid}", "url": link.replace("~thumb", "~large"), "text": text,
                                "photo": True, "src": "nasa"})
        return out
    except Exception as e:
        _log(f"NASA error ({q}): {str(e)[:100]}")
        return []


def archive(q):
    """Internet Archive (archive.org): lakhon free (CC / public domain) asli videos - travel, shehar, khaane.
    Sirf woh jin ka license commercial use allow karta hai; 120MB se chhoti mp4."""
    try:
        lic = "(licenseurl:*creativecommons.org/licenses/by/* OR licenseurl:*creativecommons.org/licenses/by-sa/* " \
              "OR licenseurl:*publicdomain* OR licenseurl:*creativecommons.org/licenses/cc0*)"
        r = requests.get("https://archive.org/advancedsearch.php", timeout=40, headers=UA, params={
            "q": f"({q[:80]}) AND mediatype:movies AND {lic}", "fl[]": ["identifier", "title", "subject", "description"],
            "rows": 12, "output": "json"})
        docs = r.json().get("response", {}).get("docs", [])
        out = []
        for d in docs[:8]:
            ident = d.get("identifier")
            if not ident:
                continue
            try:
                m = requests.get(f"https://archive.org/metadata/{ident}", timeout=30, headers=UA).json()
            except Exception:
                continue
            files = [f for f in m.get("files", []) if str(f.get("name", "")).lower().endswith(".mp4")
                     and 2e6 < float(f.get("size") or 0) < 120e6]
            if not files:
                continue
            f = sorted(files, key=lambda f: -float(f.get("height") or f.get("size") or 0))[0]
            if f.get("height") and float(f["height"]) < 480:
                continue
            subj = d.get("subject") or ""
            subj = " ".join(subj) if isinstance(subj, list) else str(subj)
            desc = d.get("description") or ""
            desc = " ".join(desc) if isinstance(desc, list) else str(desc)
            text = _clean(f"{d.get('title', '')} {subj} {desc[:300]}")
            dur = float(f.get("length") or 20) if str(f.get("length") or "").replace(".", "").isdigit() else 20
            if dur < 4:
                continue
            out.append({"id": f"ia{ident}", "url": f"https://archive.org/download/{ident}/{f['name']}",
                        "text": text, "dur": min(dur, 60), "src": "archive", "vertical": False,
                        "credit": f"{d.get('title', ident)[:60]} / Internet Archive"})
        return out
    except Exception as e:
        _log(f"Archive error: {str(e)[:120]}")
        return []


def mixkit(q):
    """Mixkit.co: muft HD stock videos (license: commercial + YouTube allowed, attribution zaroori nahi).
    Har cheez/jagah ka apna tag page - JSON-LD mein naam + mp4 link."""
    import json as _j
    out = []
    try:
        slug = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")[:60]
        if not slug:
            return []
        for u in (f"https://mixkit.co/free-stock-video/{slug}/", f"https://mixkit.co/free-stock-video/discover/{slug}/"):
            r = requests.get(u, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"})
            if r.status_code != 200:
                continue
            for blk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.S):
                try:
                    data = _j.loads(blk)
                except Exception:
                    continue
                items = data.get("@graph", [data]) if isinstance(data, dict) else data
                for v in items:
                    if not isinstance(v, dict) or v.get("@type") != "VideoObject" or not v.get("contentUrl"):
                        continue
                    m = re.search(r"/videos/(\d+)/", v["contentUrl"])
                    if not m:
                        continue
                    d = re.search(r"(\d+)M(\d+)S", str(v.get("duration") or ""))
                    dur = int(d.group(1)) * 60 + int(d.group(2)) if d else 15
                    out.append({"id": f"mk{m.group(1)}", "url": v["contentUrl"], "text": _clean(v.get("name", "")),
                                 "dur": min(max(dur, 5), 60), "src": "mixkit", "vertical": False, "credit": f"{v.get('name', '')[:60]} / Mixkit"})
            if out:
                break
    except Exception as e:
        _log(f"Mixkit error: {str(e)[:120]}")
    return out[:20]


def videos(q, vertical=False):
    """Har platform se is cheez ki videos."""
    return pixabay_videos(q, vertical) + pexels_videos(q, vertical) + commons(q, True) + nasa(q, True) + archive(q) + mixkit(q)


# ---------------------------------------------------------------- photos
def pixabay_photos(q):
    if not PIXABAY_KEY:
        return []
    try:
        r = requests.get("https://pixabay.com/api/", timeout=40, params={
            "key": PIXABAY_KEY, "q": q[:90], "image_type": "photo", "safesearch": "true", "per_page": 30,
            "min_width": 1600})
        return [{"id": f"pxi{h['id']}", "url": h["largeImageURL"], "text": (h.get("tags") or "").lower(),
                 "photo": True, "src": "pixabay"} for h in r.json().get("hits", []) if h.get("largeImageURL")]
    except Exception as e:
        _log(f"Pixabay photo error ({q}): {str(e)[:100]}")
        return []


def pexels_photos(q):
    if not PEXELS_KEY:
        return []
    try:
        r = requests.get("https://api.pexels.com/v1/search", timeout=40, headers={"Authorization": PEXELS_KEY},
                         params={"query": q[:90], "per_page": 30})
        return [{"id": f"pei{p['id']}", "url": p["src"]["large2x"], "photo": True, "src": "pexels",
                 "text": ((p.get("alt") or "") + " " + (p.get("url") or "").replace("-", " ")).lower()}
                for p in r.json().get("photos", []) if p.get("src", {}).get("large2x")]
    except Exception as e:
        _log(f"Pexels photo error ({q}): {str(e)[:100]}")
        return []


def openverse(q):
    """Openverse: Flickr aur doosri sites ki 80 crore+ free photos (commercial use wali)."""
    try:
        r = requests.get("https://api.openverse.org/v1/images/", headers=UA, timeout=40, params={
            "q": q[:90], "page_size": 20, "license_type": "commercial,modification", "size": "large", "mature": "false"})
        out = []
        for h in r.json().get("results", []):
            if (h.get("width") or 0) < 1000 or not h.get("url"):
                continue
            tags = " ".join(t.get("name", "") for t in (h.get("tags") or []))
            out.append({"id": f"ov{h['id']}", "url": h["url"], "text": _clean(f"{h.get('title', '')} {tags}"),
                        "photo": True, "src": "openverse"})
        return out
    except Exception as e:
        _log(f"Openverse error ({q}): {str(e)[:100]}")
        return []


def photos(q):
    return pixabay_photos(q) + pexels_photos(q) + commons(q, False) + openverse(q) + nasa(q, False)


# ---------------------------------------------------------------- helpers
def match_score(text, words):
    """Kitne lafz match hue (sab lafz = sab se behtar)."""
    return sum(1 for w in words if w in (text or ""))


def words(q):
    return [w for w in re.findall(r"[a-z]+", (q or "").lower()) if len(w) > 2]


def download(url, path, min_size=30000):
    with requests.get(url, stream=True, timeout=180, headers=UA) as resp:
        resp.raise_for_status()
        with open(path, "wb") as f:
            for chunk in resp.iter_content(1 << 20):
                f.write(chunk)
    return os.path.getsize(path) >= min_size


def photo_to_clip(img, out, w, h, secs=8, fps=30):
    """Photo ko video jaisa banao: har dafa alag camera harkat (andar/bahar zoom, pan, tilt, tirchha),
    narm ease, halka vignette aur film grain - dekhne wale ko tasveer nahi, shot lage."""
    import random
    fr = int(secs * fps)
    e = f"(0.5-0.5*cos(PI*on/{fr}))"
    moves = [
        (f"1.05+0.22*{e}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        (f"1.27-0.22*{e}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        ("1.22", f"(iw-iw/zoom)*{e}", "ih/2-(ih/zoom/2)"),
        ("1.22", f"(iw-iw/zoom)*(1-{e})", "ih/2-(ih/zoom/2)"),
        ("1.22", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*(1-{e})"),
        (f"1.08+0.16*{e}", f"(iw-iw/zoom)*{e}", f"(ih-ih/zoom)*{e}"),
        (f"1.24-0.14*{e}", f"(iw-iw/zoom)*(1-{e})", f"(ih-ih/zoom)*0.3"),
    ]
    z, x, y = random.choice(moves)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", img, "-vf",
                    f"scale={w * 3}:{h * 3}:force_original_aspect_ratio=increase,crop={w * 3}:{h * 3},"
                    f"zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s={w}x{h}:fps={fps},"
                    "vignette=PI/5,noise=alls=6:allf=t,eq=contrast=1.04:saturation=1.08,"
                    "format=yuv420p", "-frames:v", str(fr), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out],
                   check=True, capture_output=True)


def frame(src, jpg, at=None):
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if at is not None:
        cmd += ["-ss", f"{at:.1f}"]
    cmd += ["-i", src, "-frames:v", "1", "-vf", "scale=640:-2", jpg]
    subprocess.run(cmd, capture_output=True)
    return os.path.exists(jpg)


def scene_terms(sc, default=""):
    """Scene ke 'visuals' (jis tarteeb se cheezein boli ja rahi hain) - purane 'visual' ke saath bhi chale."""
    terms = [t.strip() for t in (sc.get("visuals") or []) if isinstance(t, str) and t.strip()]
    v = (sc.get("visual") or "").strip()
    if not terms and v:
        terms = [v]
    return terms or ([default] if default else [])


VISUALS_RULE = ("Also give 'visuals': a list of 1-4 short ENGLISH stock-footage search terms, IN THE ORDER the "
                "narration mentions them, so the picture changes exactly when the words change (e.g. if the "
                "scene says 'in Turkey people eat kebab and drink tea by the Bosphorus' -> "
                "[\"turkish kebab\", \"turkish tea glass\", \"bosphorus istanbul\"]). Each term must be the SPECIFIC "
                "thing said (that country's dish, that animal, that place, that object) - never a generic word. "
                "If a country/city is being talked about, put its name in the term.")
