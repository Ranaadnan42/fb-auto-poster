"""
Funny Videos page - lambi (5-6 min) mazahiya kahani videos.
Style baari baari: "ai" (Pixabay ki AI-generated tasveerein) aur "cartoon" (Pixabay cartoon tasveerein).
Har tasveer par aahista zoom/pan (Ken Burns), Urdu narration, subtitles aur har scene ka meme caption.
Sab free: Gemini (text), Edge TTS (awaaz), Pixabay (tasveerein).
"""
import os
import json
import random
import shutil

import requests

import funny as F

STYLE_QUERY = {
    "ai": {"suffix": "ai generated", "tag": "ai generated"},
    "cartoon": {"suffix": "cartoon", "tag": "cartoon"},
}
USED_IMAGES = set()


PARTS = 3
PART_NAMES = {1: "قسط 1", 2: "قسط 2", 3: "آخری قسط"}


def series_state(history, force_style=None):
    """Roz style badalta hai (cartoon / ai). Har style ki apni series qiston mein aage barhti hai."""
    longs = [h for h in history if h.get("series")]
    style = force_style or ("cartoon" if len(longs) % 2 == 0 else "ai")
    mine = [h for h in longs if h.get("style") == style]
    if mine and mine[-1].get("part", PARTS) < PARTS:
        last = mine[-1]
        prev = [h for h in mine if h["series"] == last["series"]]
        return {"series": last["series"], "series_title": last.get("series_title", ""),
                "part": last["part"] + 1, "style": style, "topic": last.get("topic"),
                "summaries": [h.get("summary", "") for h in prev]}
    return {"series": F.datetime.datetime.utcnow().strftime("%Y%m%d%H%M") + style[0],
            "series_title": "", "part": 1, "style": style,
            "topic": F.SITUATIONS[(len(history) * 3 + 11) % len(F.SITUATIONS)], "summaries": []}


def write_story(history, st):
    style = st["style"]
    used = [h["title"] for h in history[-150:]]
    situation = st["topic"]
    p = st["part"]
    if p == 1:
        series_txt = (f"This is PART 1 of a {PARTS}-part funny series. Create memorable original "
                      "characters (never famous cartoon or TV characters). End this part on a funny "
                      "cliffhanger, last line: \"آگے کیا ہوا؟ اگلی قسط ضرور دیکھیں\"")
    else:
        prev = "\n".join(f"Part {i + 1}: {s}" for i, s in enumerate(st["summaries"]))
        series_txt = (f"This is PART {p} of {PARTS} of the series \"{st['series_title']}\". "
                      f"Story so far:\n{prev}\nContinue with the SAME characters and names. "
                      + ("End on a funny cliffhanger, last line: \"آگے کیا ہوا؟ اگلی قسط ضرور دیکھیں\""
                         if p < PARTS else
                         "This is the FINAL part: resolve everything with the biggest, most surprising funny twist."))
    look = ("realistic, colourful AI-art scenes" if style == "ai" else "bright 2D cartoon scenes")
    extra, best = "", None
    for _ in range(3):
        data = F.ask_json(f"""You write a 5-6 minute FUNNY story video in URDU for the Pakistani Facebook
page "{F.PAGE_NAME}". Topic: {situation}. The visuals will be {look}.
{series_txt}
Never reuse an idea from these past titles: {json.dumps(used, ensure_ascii=False)}

Make it genuinely funny: one desi main character with a funny name (e.g. Chacha Bashir, Pappu,
Mamoon Jaan), a simple plan that goes hilariously wrong step by step, exaggeration, funny
dialogue lines inside the narration, desi references (ammi, chai, biryani, rishta, cricket,
load shedding), and a big surprising twist at the end. Line 1 must be a hook.
Very end (after the cliffhanger or ending): "کہانی پسند آئی ہو تو پیج فالو کریں"
{F.RULES}
{extra}

Split into exactly 12 scenes, each about 80 words (total about 950 words - count carefully).
For each scene give "visual": a 1-3 word ENGLISH image search term for what is shown
(simple, common things: "old man", "goat", "wedding", "kitchen", "cricket", "angry woman",
"village", "car", "rain", "money"), and "meme": a very short funny Urdu header (max 7 words).

Return JSON: {{"series_title": "short funny Urdu name of the series (keep the same name in every part)",
 "summary": "3-4 English sentences summarising what happened in THIS part (for the next part)",
 "scenes": [{{"text": "...", "visual": "...", "meme": "..."}}],
 "caption": "2 funny Urdu lines asking people to comment",
 "hashtags": ["#funny", "..."] (8 hashtags, English and Urdu)}}""")
        n = F.word_count(data)
        F.log(f"Story script: {n} words")
        if len(data.get("scenes", [])) >= 6 and (best is None or n > F.word_count(best)):
            best = data
        if n >= 820:
            break
        extra = f"IMPORTANT: your last draft had only {n} words. Each scene must be about 90 words."
    if not best:
        raise RuntimeError("Kahani nahi bani")
    stitle = st["series_title"] or best.get("series_title") or "مزاحیہ کہانی"
    best.update({"animal": style, "topic": situation, "series": st["series"], "series_title": stitle,
                 "part": p, "style": style, "title": f"{stitle} | {PART_NAMES[p]}"})
    return best


def pixabay_images(query, count, job, prefix, style):
    got = []
    sq = STYLE_QUERY[style]
    for q, strict in ((f"{query} {sq['suffix']}", True), (query, True),
                      (f"{query} {sq['suffix']}", False), (sq["suffix"], True)):
        if len(got) >= count:
            break
        try:
            r = requests.get("https://pixabay.com/api/", timeout=40, params={
                "key": F.PIXABAY_KEY, "q": q, "safesearch": "true", "per_page": 50,
                "image_type": "illustration" if style == "ai" else "all",
                "orientation": "horizontal"})
            r.raise_for_status()
            hits = [h for h in r.json().get("hits", []) if h["id"] not in USED_IMAGES
                    and (not strict or sq["tag"] in h.get("tags", "").lower())]
        except Exception as e:
            F.log(f"Pixabay image error ({q}): {str(e)[:150]}")
            continue
        random.shuffle(hits)
        for h in hits:
            if len(got) >= count:
                break
            url = h.get("largeImageURL") or h.get("webformatURL")
            if not url:
                continue
            path = os.path.join(job, f"{prefix}_{len(got)}.jpg")
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
                with open(path, "wb") as f:
                    f.write(resp.content)
                if os.path.getsize(path) > 20000:
                    USED_IMAGES.add(h["id"])
                    got.append(path)
            except Exception as e:
                F.log(f"Image download fail: {str(e)[:150]}")
    return got


def build_scene(job, i, sc, w, h, style, title):
    text = (sc.get("text") or "").strip()
    audio = f"a{i}.mp3"
    F.tts(text, os.path.join(job, audio))
    dur = F.duration(os.path.join(job, audio)) + 0.4
    k = max(1, min(4, round(dur / 7)))                     # har ~7 sec nayi tasveer
    imgs = pixabay_images(sc.get("visual") or "funny", k, job, f"i{i}", style)
    F.REPORT["stock_clips"] = F.REPORT.get("stock_clips", 0) + len(imgs)
    if not imgs:
        F.REPORT["fallback_clips"] = F.REPORT.get("fallback_clips", 0) + 1
        fb = os.path.join(job, f"i{i}_fb.mp4")
        F.fallback_clip(fb, w, h)
        imgs = [fb]
    k = len(imgs)
    seg = dur / k
    F.make_ass(os.path.join(job, f"s{i}.ass"), text, dur - 0.4, w, h,
               title if i == 0 else None, sc.get("meme"))
    cmd = ["ffmpeg", "-y"]
    for p in imgs:
        if p.endswith(".mp4"):
            cmd += ["-stream_loop", "-1", "-t", f"{seg + 0.2:.2f}", "-i", os.path.basename(p)]
        else:
            cmd += ["-loop", "1", "-framerate", "30", "-t", f"{seg + 0.2:.2f}", "-i", os.path.basename(p)]
    cmd += ["-i", audio]
    frames = int(seg * 30) + 6
    chains = []
    for j in range(k):
        zin = (i + j) % 2 == 0
        z = "min(1.0+0.0009*on,1.18)" if zin else "max(1.18-0.0009*on,1.0)"
        px = "iw/2-(iw/zoom/2)" if (i + j) % 3 else "(iw-iw/zoom)*on/" + str(frames)
        chains.append(
            f"[{j}:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
            f"zoompan=z='{z}':x='{px}':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30,"
            f"trim=duration={seg:.2f},setpts=PTS-STARTPTS,setsar=1,"
            f"fade=t=in:st=0:d=0.3[v{j}]")
    fontsdir = f":fontsdir={F.FONTS_DIR}" if os.path.isdir(F.FONTS_DIR) else ""
    chains.append("".join(f"[v{j}]" for j in range(k)) +
                  f"concat=n={k}:v=1:a=0,eq=saturation=1.15,subtitles=s{i}.ass{fontsdir},format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(chains), "-map", "[v]", "-map", f"{k}:a:0",
            "-af", "apad", "-t", f"{dur:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", f"p{i}.mp4"]
    F.run(cmd, cwd=job)
    return f"p{i}.mp4"


def build_long(history, out_path, force_style=None):
    st = series_state(history, force_style if force_style in STYLE_QUERY else None)
    style = st["style"]
    script = write_story(history, st)
    job = os.path.join(F.WORK, f"story_{style}")
    shutil.rmtree(job, ignore_errors=True)
    os.makedirs(job)
    scenes = [s for s in script["scenes"] if (s.get("text") or "").strip()]
    parts = []
    for i, sc in enumerate(scenes):
        parts.append(build_scene(job, i, sc, 1920, 1080, style, script["title"]))
        F.log(f"story: scene {i + 1}/{len(scenes)} ready")
    with open(os.path.join(job, "list.txt"), "w") as f:
        f.writelines(f"file '{p}'\n" for p in parts)
    F.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy",
           "-movflags", "+faststart", os.path.abspath(out_path)], cwd=job)
    return script
