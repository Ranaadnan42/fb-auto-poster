"""
AutoPilot AI - customer DEMO maker (Web Builder ki social media service ke liye).

Har business (sales bot ke leads mein se) ke liye uski APNI website se:
  - tasveerein (products / dishes / dukan) aur logo uthata hai
  - website ki likhai parh kar AI se chhota reel script banwata hai (sirf website ke facts, koi qeemat nahi)
  - 1 reel (9:16, awaaz + subtitles + business ka naam/logo) aur 2 pics (1080x1350) banata hai
Yeh sirf DEMO banata hai - kahin post nahi karta.

Input:  demo_queue.json  -> [{"id","name","biz_type","city","country","website"}, ...]
Output: demo_out/<slug>/reel.mp4, post1.jpg, post2.jpg, info.json
Env:    GEMINI_API_KEY (GROQ_API_KEY backup), PIXABAY_API_KEY (agar website par tasveerein kam hon)
"""
import os
import io
import re
import sys
import json
import time
import random
import asyncio
import subprocess
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

QUEUE = os.environ.get("DEMO_QUEUE", "demo_queue.json")
OUT = os.path.abspath("demo_out")
FONTS = os.path.abspath("fonts")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY")
MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite"]
W, H = 1080, 1920
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
VOICES = {"en": ("en-US-AndrewNeural", "+4%"), "ar": ("ar-SA-HamedNeural", "+0%")}
GULF = {"UAE", "Saudi Arabia", "Qatar", "Kuwait", "Oman", "Bahrain"}
STOCK_Q = {"restaurant": "restaurant food", "cafe": "coffee cafe", "fast_food": "burger", "clothes": "fashion clothes",
           "hairdresser": "hair salon", "beauty": "beauty salon", "bakery": "bakery bread", "pharmacy": "pharmacy",
           "supermarket": "grocery", "dentist": "dentist", "clinic": "clinic", "jewelry": "jewelry"}


def log(m):
    print(m, flush=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} fail: {r.stderr[-500:]}")
    return r.stdout


def duration(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", p]).strip())


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "biz").lower()).strip("-")[:40] or "biz"


def font(size, arabic=False):
    name = "NotoNaskhArabic-Bold.ttf" if arabic else "NotoSans-Bold.ttf"
    try:
        return ImageFont.truetype(os.path.join(FONTS, name), size)
    except Exception:
        return ImageFont.load_default()


# ------------------------------------------------------------- website reading
def fetch(url, timeout=25):
    r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r


def page_text(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    desc = re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html)
    body = re.sub(r"(?s)<[^>]+>", " ", html)
    body = re.sub(r"&[a-z#0-9]+;", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    parts = [title.group(1).strip() if title else "", desc.group(1).strip() if desc else "", body[:3500]]
    return "\n".join(p for p in parts if p)


def image_urls(html, base):
    found = []
    for m in re.finditer(r'(?is)<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html):
        found.append(("og", m.group(1)))
    for m in re.finditer(r"(?is)<img\b([^>]+)>", html):
        tag = m.group(1)
        src = None
        for attr in ("data-src", "data-lazy-src", "data-original", "src"):
            a = re.search(attr + r'\s*=\s*["\']([^"\']+)', tag)
            if a and not a.group(1).startswith("data:"):
                src = a.group(1)
                break
        ss = re.search(r'srcset\s*=\s*["\']([^"\']+)', tag)
        if ss:   # srcset mein sab se bari
            cands = [c.strip().split(" ")[0] for c in ss.group(1).split(",") if c.strip()]
            if cands:
                src = cands[-1]
        if src:
            kind = "logo" if re.search(r"logo", tag, re.I) else "img"
            found.append((kind, src))
    for m in re.finditer(r'(?is)background-image\s*:\s*url\(["\']?([^"\')]+)', html):
        found.append(("img", m.group(1)))
    out, seen = [], set()
    for kind, u in found:
        u = urljoin(base, u.strip())
        if not u.startswith("http") or u in seen or re.search(r"\.(svg|gif)(\?|$)", u, re.I):
            continue
        if re.search(r"(icon|sprite|pixel|tracking|placeholder|spinner|loader|avatar|badge|payment|flag)", u, re.I) \
                and kind != "logo":
            continue
        seen.add(u)
        out.append((kind, u))
    return out


def is_graphic(img):
    """Logo / likhai wali graphic: bohat kam rang."""
    small = img.convert("RGB").resize((64, 64))
    return len(set(small.getdata())) < 700


def ahash(img):
    g = img.convert("L").resize((8, 8))
    px = list(g.getdata())
    avg = sum(px) / 64
    return sum(1 << i for i, v in enumerate(px) if v > avg)


def grab_images(url, folder):
    """Website (aur 1-2 andar ke pages) se asli tasveerein aur logo."""
    photos, logo, text, pages = [], None, "", [url]
    try:
        r = fetch(url)
        html, base = r.text, r.url
    except Exception as e:
        log(f"  website nahi khuli: {str(e)[:120]}")
        return photos, logo, text
    text = page_text(html)
    host = urlparse(base).netloc
    for m in re.finditer(r'(?is)href=["\']([^"\'#]+)', html):
        u = urljoin(base, m.group(1))
        if urlparse(u).netloc == host and re.search(r"(menu|gallery|shop|collection|service|about|product)", u, re.I):
            if u not in pages:
                pages.append(u)
        if len(pages) >= 3:
            break
    cands = image_urls(html, base)
    for p in pages[1:]:
        try:
            r2 = fetch(p, 20)
            cands += image_urls(r2.text, r2.url)
            text += "\n" + page_text(r2.text)[:1500]
        except Exception:
            pass
    seen_sizes = set()
    for kind, u in cands:
        if len(photos) >= 10 and logo:
            break
        try:
            r = requests.get(u, headers=UA, timeout=25)
            if r.status_code != 200 or len(r.content) < 8000:
                continue
            img = Image.open(io.BytesIO(r.content))
            img.load()
        except Exception:
            continue
        w, h = img.size
        if kind == "logo" and not logo and w >= 80:
            path = os.path.join(folder, "logo.png")
            img.convert("RGBA").save(path)
            logo = path
            continue
        if w < 600 or h < 400 or len(photos) >= 10:
            continue
        if re.search(r"logo", u, re.I) or is_graphic(img):   # logo/banner graphic - asli tasveer nahi
            continue
        hsh = ahash(img)
        if any(bin(hsh ^ o).count("1") <= 6 for o in seen_sizes):   # takreeban wahi tasveer
            continue
        seen_sizes.add(hsh)
        path = os.path.join(folder, f"photo_{len(photos)}.jpg")
        img.convert("RGB").save(path, quality=92)
        photos.append(path)
    log(f"  tasveerein: {len(photos)}, logo: {'haan' if logo else 'nahi'}")
    return photos, logo, text


def stock_photos(biz_type, folder, need):
    got = []
    if not PIXABAY_KEY or need <= 0:
        return got
    q = STOCK_Q.get(biz_type, biz_type.replace("_", " "))
    try:
        r = requests.get("https://pixabay.com/api/", timeout=30, params={
            "key": PIXABAY_KEY, "q": q, "image_type": "photo", "safesearch": "true", "per_page": 30,
            "min_width": 1080})
        hits = r.json().get("hits", [])
        random.shuffle(hits)
        for h in hits[:need]:
            img = requests.get(h["largeImageURL"], timeout=40).content
            path = os.path.join(folder, f"stock_{len(got)}.jpg")
            with open(path, "wb") as f:
                f.write(img)
            got.append(path)
    except Exception as e:
        log(f"  pixabay fail: {str(e)[:100]}")
    return got


# ------------------------------------------------------------- AI script
def ask_json(prompt):
    last = None
    if GEMINI_KEY:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_KEY)
        for model in MODELS:
            try:
                res = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.8))
                return json.loads(res.text)
            except Exception as e:
                last = e
                log(f"  {model}: {str(e)[:120]}")
                time.sleep(3)
    import groq_backup
    if groq_backup.enabled():
        return groq_backup.ask_json(prompt, 0.8, log)
    raise RuntimeError(f"AI fail: {last}")


PRICE_RE = re.compile(r"[$€£]|\b(usd|aed|sar|price|prices|cost|cheap|discount|\d+\s*%\s*off)\b", re.I)


def write_script(biz, text, lang):
    lang_name = "Arabic (simple Gulf-friendly Modern Standard Arabic)" if lang == "ar" else "English"
    prompt = f"""You write a short, high-energy social media reel (about 25 seconds) promoting this real business.
Business name: {biz['name']}
Type: {biz['biz_type']}
City: {biz.get('city')}, {biz.get('country')}
Text from their own website (use ONLY facts found here, never invent dishes, products, awards or offers):
---
{text[:4500]}
---
Rules:
- Language for narration and labels: {lang_name}.
- Sound like the business's own social media post, warm and inviting, speaking to local customers.
- NO prices, NO discounts, NO phone numbers, NO made-up claims.
- 5 scenes. Scene 1 is a strong hook. Last scene invites people to visit / order / book (use what the website offers).
- Each "say" is max 16 words. Each "label" is 2-4 catchy words shown on screen about THAT scene's content
  (never words like "hook", "intro", "scene", "CTA", "outro").
Return JSON:
{{"scenes":[{{"say":"...","label":"..."}}], "caption":"2-3 line post caption with 4-6 relevant local hashtags",
 "post1":{{"title":"max 5 words","line":"max 12 words"}}, "post2":{{"title":"max 5 words","line":"max 12 words"}}}}"""
    for _ in range(3):
        data = ask_json(prompt)
        sc = [s for s in data.get("scenes", []) if s.get("say")]
        blob = json.dumps(data, ensure_ascii=False)
        bad = any(re.fullmatch(r"(hook|intro|scene \d*|cta|outro|call to action)", (x.get("label") or "").strip(), re.I)
                  for x in sc)
        if len(sc) >= 4 and not PRICE_RE.search(blob) and not bad:
            data["scenes"] = sc[:6]
            return data
        log("  script mein masla (qeemat ya kam scenes), dobara")
    data["scenes"] = sc[:6]
    return data


# ------------------------------------------------------------- media
def tts(text, path, lang):
    import edge_tts
    voice, rate = VOICES[lang]

    async def go():
        await edge_tts.Communicate(text, voice, rate=rate).save(path)
    for attempt in range(5):
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            log(f"  TTS retry: {str(e)[:100]}")
        time.sleep(4 * (attempt + 1))
    raise RuntimeError("awaaz nahi bani")


def photo_clip(img, out, secs):
    fr = int(secs * 30) + 6
    e = f"(0.5-0.5*cos(PI*on/{fr}))"
    z, x, y = random.choice([
        (f"1.04+0.18*{e}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        (f"1.22-0.18*{e}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        ("1.18", f"(iw-iw/zoom)*{e}", "ih/2-(ih/zoom/2)"),
        ("1.18", f"(iw-iw/zoom)*(1-{e})", "ih/2-(ih/zoom/2)"),
    ])
    # tasveer poori dikhe: peeche wahi tasveer blur, aage poori tasveer - phir camera harkat
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", img, "-filter_complex",
         f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,eq=brightness=-0.12[bg];"
         f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
         f"[bg][fg]overlay=(W-w)/2:(H-h)/2,scale={W * 2}:{H * 2},"
         f"zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s={W}x{H}:fps=30,"
         "vignette=PI/5,eq=contrast=1.05:saturation=1.1,format=yuv420p",
         "-frames:v", str(fr), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", out])


def music(path, secs):
    root = random.choice([196.0, 220.0, 246.9])
    parts = []
    for k, ch in enumerate([[1, 1.25, 1.5], [0.84, 1.0, 1.26], [0.89, 1.12, 1.33], [0.75, 0.94, 1.12]]):
        env = f"(0.5+0.5*sin(2*PI*t/8-{k}*PI/2))"
        parts += [f"0.045*sin(2*PI*{root * m:.2f}*t)*{env}" for m in ch]
    parts.append("0.05*sin(2*PI*55*t)*exp(-8*mod(t,0.5))")   # halki beat
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc='{'+'.join(parts)}':s=44100:d={secs + 1:.1f}",
         "-af", f"lowpass=f=2600,afade=t=in:d=1,afade=t=out:st={max(secs - 2, 1):.1f}:d=2",
         "-ac", "2", "-c:a", "aac", "-b:a", "128k", path])


def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def esc(s):
    return (s or "").replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def make_ass(path, biz, sub, label, dur, lang, domain):
    sub_font = "Noto Naskh Arabic" if lang == "ar" else "Noto Sans"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Name,Noto Sans,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,4,2,8,60,60,140,1
Style: Label,{sub_font},88,&H0033D7FF,&H0033D7FF,&H00000000,&H64000000,1,0,0,0,100,100,1,0,1,5,3,8,60,60,250,1
Style: Sub,{sub_font},{78 if lang == 'ar' else 66},&H00FFFFFF,&H00FFFFFF,&H90000000,&H90000000,1,0,0,0,100,100,0,0,3,16,0,2,80,80,520,1
Style: Site,Noto Sans,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,1,0,1,3,2,2,40,40,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [f"Dialogue: 0,{ass_time(0)},{ass_time(dur + 1)},Name,,0,0,0,,{esc(biz['name']).upper()}",
          f"Dialogue: 0,{ass_time(0)},{ass_time(dur + 1)},Site,,0,0,0,,{esc(domain)}"]
    if label:
        ev.append(f"Dialogue: 1,{ass_time(0.1)},{ass_time(dur)},Label,,0,0,0,,{{\\fad(250,250)}}{esc(label).upper()}")
    words = sub.split()
    chunks = [" ".join(words[i:i + 4]) for i in range(0, len(words), 4)]
    weights = [len(c) + 3 for c in chunks]
    scale = dur / max(sum(weights), 1)
    t = 0.0
    for c, wg in zip(chunks, weights):
        ev.append(f"Dialogue: 2,{ass_time(t)},{ass_time(t + wg * scale)},Sub,,0,0,0,,{esc(c)}")
        t += wg * scale
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(ev) + "\n")


def build_reel(biz, script, photos, logo, folder, lang, domain):
    parts = []
    for i, sc in enumerate(script["scenes"]):
        voice = os.path.join(folder, f"v{i}.mp3")
        tts(sc["say"], voice, lang)
        dur = duration(voice) + 0.35
        clip = os.path.join(folder, f"c{i}.mp4")
        photo_clip(photos[i % len(photos)], clip, dur)   # photos pehle hi alag-alag hain
        ass = os.path.join(folder, f"s{i}.ass")
        make_ass(ass, biz, sc["say"], sc.get("label", ""), dur, lang, domain)
        out = os.path.join(folder, f"p{i}.mp4")
        vf = f"subtitles={os.path.basename(ass)}:fontsdir={FONTS}"
        inputs = ["-i", os.path.basename(clip), "-i", os.path.basename(voice)]
        if logo:
            inputs += ["-i", os.path.basename(logo)]
            fc = (f"[2:v]scale=180:180:force_original_aspect_ratio=decrease,format=rgba[lg];"
                  f"[0:v][lg]overlay=W-w-40:40,{vf}[v]")
        else:
            fc = f"[0:v]{vf}[v]"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc,
                        "-map", "[v]", "-map", "1:a", "-t", f"{dur:.2f}", "-af", "apad",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-r", "30",
                        "-c:a", "aac", "-ar", "44100", "-ac", "2", os.path.basename(out)],
                       cwd=folder, check=True, capture_output=True)
        parts.append(out)
    lst = os.path.join(folder, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.basename(p)}'\n" for p in parts)
    joined = os.path.join(folder, "joined.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
                    "-c", "copy", "joined.mp4"], cwd=folder, check=True, capture_output=True)
    total = duration(joined)
    bgm = os.path.join(folder, "bgm.m4a")
    music(bgm, total)
    final = os.path.join(folder, "reel.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", bgm, "-filter_complex",
         "[1:a]volume=0.5[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", final])
    for p in parts + [joined, bgm]:
        os.remove(p)
    return final


def wrap(draw, text, fnt, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_post(photo, logo, biz, title, line, path, lang, domain, accent):
    PW, PH = 1080, 1350
    img = ImageOps.fit(Image.open(photo).convert("RGB"), (PW, PH), Image.LANCZOS)
    grad = Image.new("L", (1, PH))
    for y in range(PH):
        grad.putpixel((0, y), int(max(0, (y - PH * 0.42) / (PH * 0.58)) * 235))
    dark = Image.new("RGB", (PW, PH), (0, 0, 0))
    img = Image.composite(dark, img, grad.resize((PW, PH)))
    d = ImageDraw.Draw(img)
    ar = lang == "ar"
    tf, lf, sf = font(84, ar), font(46, ar), font(36)
    y = PH - 120
    d.text((60, y), domain, font=sf, fill=(230, 230, 230))
    body = wrap(d, line or "", lf, PW - 120)
    y -= 30 + 58 * len(body)
    for i, l in enumerate(body):
        d.text((60, y + i * 58), l, font=lf, fill=(255, 255, 255))
    heads = wrap(d, (title or biz["name"]).upper(), tf, PW - 120)
    y -= 20 + 96 * len(heads)
    for i, l in enumerate(heads):
        d.text((60, y + i * 96), l, font=tf, fill=accent)
    d.rectangle([60, y - 26, 200, y - 16], fill=accent)
    if logo:
        try:
            lg = Image.open(logo).convert("RGBA")
            lg.thumbnail((200, 200))
            pad = Image.new("RGBA", (lg.width + 30, lg.height + 30), (255, 255, 255, 230))
            pad.paste(lg, (15, 15), lg)
            img.paste(pad, (PW - pad.width - 40, 40), pad)
        except Exception:
            pass
    else:
        d.text((60, 50), biz["name"].upper(), font=font(44), fill=(255, 255, 255))
    img.save(path, quality=92)


def process(biz):
    slug = slugify(biz["name"])
    folder = os.path.join(OUT, slug)
    os.makedirs(folder, exist_ok=True)
    lang = "ar" if biz.get("country") in GULF and biz.get("lang") == "ar" else biz.get("lang", "en")
    log(f"\n=== {biz['name']} ({biz['biz_type']}, {biz.get('city')}) ===")
    photos, logo, text = grab_images(biz["website"], folder)
    own = len(photos)
    if len(photos) < 3:
        photos += stock_photos(biz["biz_type"], folder, 5 - len(photos))
    if not photos:
        raise RuntimeError("koi tasveer nahi mili")
    domain = urlparse(biz["website"]).netloc.replace("www.", "")
    script = write_script(biz, text or biz["name"], lang)
    log(f"  script: {[s['say'] for s in script['scenes']]}")
    reel = build_reel(biz, script, photos, logo, folder, lang, domain)
    accent = random.choice([(255, 196, 0), (64, 224, 208), (255, 120, 90)])
    p1, p2 = script.get("post1") or {}, script.get("post2") or {}
    make_post(photos[0], logo, biz, p1.get("title"), p1.get("line"), os.path.join(folder, "post1.jpg"),
              lang, domain, accent)
    make_post(photos[min(1, len(photos) - 1) if len(photos) < 3 else 2], logo, biz, p2.get("title"),
              p2.get("line"), os.path.join(folder, "post2.jpg"), lang, domain, accent)
    for f in os.listdir(folder):   # sirf natija rakho
        if f not in ("reel.mp4", "post1.jpg", "post2.jpg"):
            os.remove(os.path.join(folder, f))
    with open(os.path.join(folder, "info.json"), "w", encoding="utf-8") as f:
        json.dump({**biz, "lang": lang, "caption": script.get("caption"),
                   "reel_secs": round(duration(reel), 1), "own_photos": own},
                  f, ensure_ascii=False, indent=1)
    log(f"  tayyar: {folder}")


def main():
    with open(QUEUE, encoding="utf-8") as f:
        queue = json.load(f)
    os.makedirs(OUT, exist_ok=True)
    ok = 0
    for biz in queue:
        try:
            process(biz)
            ok += 1
        except Exception as e:
            log(f"  FAIL {biz.get('name')}: {e}")
    log(f"\n{ok}/{len(queue)} demo tayyar")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
