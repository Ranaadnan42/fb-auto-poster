"""
WhatsApp-style chat comedy videos for the Funny Videos page.

Gemini ek mazahiya chat likhta hai (ammi-beta, dost-dost, teacher-student...),
har message "ting" ki awaaz ke saath aata hai aur do alag awaazon mein parha jata hai.
Chat bubbles ASS subtitles se bante hain (Urdu shaping libass karta hai).
"""
import os
import json
import math
import asyncio
import random
import shutil

import edge_tts

import funny as F

VOICE_ME = "ur-PK-AsadNeural"
VOICE_THEM = {"male": "ur-IN-SalmanNeural", "female": "ur-PK-UzmaNeural"}

PAIRS = [
    ("ammi and beta", "female"), ("abbu and beta", "male"), ("two best friends", "male"),
    ("teacher and student", "male"), ("wife and husband (sweet, family friendly)", "female"),
    ("chhoti behan and bhai", "female"), ("boss and lazy employee", "male"),
    ("dadi and pota", "female"), ("rishta aunty and boy", "female"),
    ("delivery rider and customer", "male"), ("cricket captain and player", "male"),
    ("landlord and tenant", "male"),
]

CHAT_RULES = F.RULES + """
- It must feel like a REAL WhatsApp chat: short messages (2-12 words each), natural desi replies,
  misunderstandings, sarcasm, exaggeration, and a big surprising punchline in the LAST message
  that makes people laugh and share.
- No emojis (they are not rendered)."""


# ---------------------------------------------------------------- script
def write_chats(history, n_chats, n_msgs):
    used = [h["title"] for h in history[-150:]]
    picks = random.sample(PAIRS, n_chats)
    topics = [F.SITUATIONS[(len(history) * 5 + i * 7) % len(F.SITUATIONS)] for i in range(n_chats)]
    plan = "\n".join(f"{i + 1}. Characters: {p[0]}. Topic: {t}" for i, (p, t) in enumerate(zip(picks, topics)))
    data = ask_chats(plan, n_chats, n_msgs, used)
    chats = data.get("chats", [])[:n_chats]
    for c, p in zip(chats, picks):
        c["them_gender"] = c.get("them_gender") or p[1]
    if not chats or any(len(c.get("messages", [])) < 4 for c in chats):
        raise RuntimeError("Chat script theek nahi bani")
    return data, chats, topics


def ask_chats(plan, n_chats, n_msgs, used):
    return F.ask_json(f"""You write viral funny WhatsApp-chat comedy videos in URDU for the Pakistani
Facebook page "{F.PAGE_NAME}". Write {n_chats} separate chat(s):
{plan}

Each chat has about {n_msgs} messages between "me" and "them" (the other person).
Never repeat ideas from these past titles: {json.dumps(used, ensure_ascii=False)}
{CHAT_RULES}

Return JSON: {{"title": "funny Urdu title for the whole video, max 60 characters",
 "caption": "1-2 funny Urdu lines asking people to tag a friend",
 "hashtags": ["#funny", "..."] (6 hashtags, English and Urdu),
 "chats": [{{"contact": "contact name as saved in phone, in Urdu, e.g. امی جان",
   "them_gender": "male or female",
   "messages": [{{"from": "me or them", "text": "..."}}]}}]}}""")


# ---------------------------------------------------------------- audio
def tts_voice(text, voice, path):
    async def go():
        await edge_tts.Communicate(text, voice, rate="+0%").save(path)
    for attempt in range(3):
        try:
            asyncio.run(go())
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            F.log(f"TTS retry {attempt + 1}: {e}")
    raise RuntimeError("Awaaz nahi bani")


def make_ting(path):
    F.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
           "sine=f=1320:d=0.09,afade=t=out:st=0.03:d=0.06,volume=0.5",
           "-f", "lavfi", "-i", "sine=f=1760:d=0.12,afade=t=out:st=0.04:d=0.08,volume=0.4",
           "-filter_complex", "[0][1]concat=n=2:v=0:a=1,aresample=44100", "-ac", "2", path])


def silence(path, secs):
    F.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo", "-t", f"{secs:.2f}", path])


# ---------------------------------------------------------------- render
def ass_color(hex_rgb):
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"&H00{b}{g}{r}".upper()


def est_lines(text, chars_per_line):
    return max(1, math.ceil(len(text) / chars_per_line))


def render_chat(chat, job, w, h, title=None):
    """Ek chat ki video (job/chat.mp4) banata hai. Wapas: file path."""
    os.makedirs(job, exist_ok=True)
    col_w = 1080
    x0 = (w - col_w) // 2
    header_h = 170 if h > w else 130
    font_size = 62 if h > w else 46
    line_h = int(font_size * 1.28)
    pad = 20
    gap = 26
    bottom = h - (260 if h > w else 60)        # reel mein Facebook buttons ke liye jagah
    top_limit = header_h + 40 + (110 if (title and h > w) else 0)
    cpl = 24 if h > w else 34
    them_voice = VOICE_THEM.get((chat.get("them_gender") or "male").lower(), VOICE_THEM["male"])

    ting = os.path.join(job, "ting.wav")
    make_ting(ting)
    pre = os.path.join(job, "pre.wav")
    silence(pre, 0.7)
    post = os.path.join(job, "post.wav")
    silence(post, 0.35)

    msgs = [m for m in chat["messages"] if (m.get("text") or "").strip()]
    timeline, audio_parts, t = [], [], 0.6
    lead = os.path.join(job, "lead.wav")
    silence(lead, 0.6)
    audio_parts.append(lead)
    for i, m in enumerate(msgs):
        mine = (m.get("from") or "").lower().startswith("me")
        typing_start = None
        if not mine:
            audio_parts.append(pre)
            typing_start = t
            t += 0.7
        v = os.path.join(job, f"v{i}.mp3")
        tts_voice(m["text"].strip(), VOICE_ME if mine else them_voice, v)
        vw = os.path.join(job, f"v{i}.wav")
        F.run(["ffmpeg", "-y", "-i", v, "-ar", "44100", "-ac", "2", vw])
        timeline.append({"t": t, "mine": mine, "text": F.ass_text(m["text"]), "typing": typing_start})
        audio_parts += [ting, vw, post]
        t += 0.21 + F.duration(vw) + 0.35
    total = t + 1.2
    tail = os.path.join(job, "tail.wav")
    silence(tail, 1.2)
    audio_parts.append(tail)

    with open(os.path.join(job, "alist.txt"), "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in audio_parts)
    audio = os.path.join(job, "audio.wav")
    F.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(job, "alist.txt"),
           "-ar", "44100", "-ac", "2", audio])

    # ---------- ASS
    green, white, header, bgc = ass_color("D9FDD3"), ass_color("FFFFFF"), ass_color("075E54"), ass_color("EFEAE2")
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Box,Noto Sans,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Me,{F.FONT},{font_size},&H00111111,&H00111111,{green},&H50000000,0,0,0,0,100,100,0,0,3,{pad},0,3,{x0 + 300},{w - x0 - col_w + 50},0,1
Style: Them,{F.FONT},{font_size},&H00111111,&H00111111,{white},&H50000000,0,0,0,0,100,100,0,0,3,{pad},0,1,{x0 + 50},{w - x0 - col_w + 300},0,1
Style: Name,{F.FONT},{int(font_size * 1.05)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1
Style: Status,Noto Sans,{int(font_size * 0.6)},&H00E0E0E0,&H00E0E0E0,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1
Style: Meme,{F.FONT},{int(font_size * 1.15)},&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,3,22,0,8,{x0 + 40},{w - x0 - col_w + 40},{header_h + 30},1
Style: Mark,Noto Sans,{30 if h > w else 26},&H60FFFFFF,&H60FFFFFF,&H80000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,9,{x0 + 30},{w - x0 - col_w + 30},{header_h + 8},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    T = F.ass_time
    ev = []
    # chat background column + header bar
    ev.append(f"Dialogue: 0,{T(0)},{T(total)},Box,,0,0,0,,{{\\pos({x0},0)\\1c{bgc}\\p1}}"
              f"m 0 0 l {col_w} 0 l {col_w} {h} l 0 {h}{{\\p0}}")
    ev.append(f"Dialogue: 1,{T(0)},{T(total)},Box,,0,0,0,,{{\\pos({x0},0)\\1c{header}\\p1}}"
              f"m 0 0 l {col_w} 0 l {col_w} {header_h} l 0 {header_h}{{\\p0}}")
    # avatar circle
    r = int(header_h * 0.3)
    cx, cy = x0 + 60 + r, header_h // 2
    k = 0.5523 * r
    ev.append(f"Dialogue: 2,{T(0)},{T(total)},Box,,0,0,0,,{{\\pos(0,0)\\1c&H00C4C4C4&\\p1}}"
              f"m {cx} {cy - r} b {cx + k:.0f} {cy - r} {cx + r} {cy - k:.0f} {cx + r} {cy} "
              f"b {cx + r} {cy + k:.0f} {cx + k:.0f} {cy + r} {cx} {cy + r} "
              f"b {cx - k:.0f} {cy + r} {cx - r} {cy + k:.0f} {cx - r} {cy} "
              f"b {cx - r} {cy - k:.0f} {cx - k:.0f} {cy - r} {cx} {cy - r}{{\\p0}}")
    name_x = cx + r + 30
    ev.append(f"Dialogue: 3,{T(0)},{T(total)},Name,,0,0,0,,{{\\pos({name_x},{int(header_h * 0.38)})}}"
              f"{F.ass_text(chat.get('contact') or 'دوست')}")
    # status: online / typing...
    status_y = int(header_h * 0.74)
    spans = []
    for m in timeline:
        if m["typing"] is not None:
            spans.append((m["typing"], m["t"]))
    cur = 0.0
    for a, b in spans:
        if a > cur:
            ev.append(f"Dialogue: 3,{T(cur)},{T(a)},Status,,0,0,0,,{{\\pos({name_x},{status_y})}}online")
        ev.append(f"Dialogue: 3,{T(a)},{T(b)},Status,,0,0,0,,{{\\pos({name_x},{status_y})}}typing...")
        cur = b
    ev.append(f"Dialogue: 3,{T(cur)},{T(total)},Status,,0,0,0,,{{\\pos({name_x},{status_y})}}online")
    if title and h > w:
        ev.append(f"Dialogue: 4,{T(0)},{T(total)},Meme,,0,0,0,,{F.ass_text(title)}")
    ev.append(f"Dialogue: 4,{T(0)},{T(total)},Mark,,0,0,0,,{F.PAGE_NAME}")

    # bubbles: har naye message par neeche se upar stack
    heights = [est_lines(m["text"], cpl) * line_h + 2 * pad for m in timeline]
    for i, m in enumerate(timeline):
        end = timeline[i + 1]["t"] if i + 1 < len(timeline) else total
        y = bottom
        for j in range(i, -1, -1):
            if y - heights[j] < top_limit:
                break
            mm = timeline[j]
            x = (x0 + col_w - 50) if mm["mine"] else (x0 + 50)
            pop = "\\fscx92\\fscy92\\t(0,120,\\fscx100\\fscy100)" if j == i else ""
            ev.append(f"Dialogue: 5,{T(m['t'])},{T(end)},{'Me' if mm['mine'] else 'Them'},,0,0,0,,"
                      f"{{\\pos({x},{y - pad}){pop}}}{mm['text']}")
            y -= heights[j] + gap
    ass = os.path.join(job, "chat.ass")
    with open(ass, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(ev) + "\n")

    out = os.path.join(job, "chat.mp4")
    fontsdir = f":fontsdir={F.FONTS_DIR}" if os.path.isdir(F.FONTS_DIR) else ""
    F.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0b141a:s={w}x{h}:r=30:d={total:.2f}",
           "-i", "audio.wav", "-vf", f"subtitles=chat.ass{fontsdir},format=yuv420p",
           "-map", "0:v", "-map", "1:a", "-shortest",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-tune", "stillimage",
           "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "chat.mp4"], cwd=job)
    return out


def build_reel(history, out_path):
    data, chats, topics = write_chats(history, 1, 14)
    job = os.path.join(F.WORK, "chat_reel")
    shutil.rmtree(job, ignore_errors=True)
    path = render_chat(chats[0], job, 1080, 1920, title=data["title"])
    shutil.copy(path, out_path)
    F.REPORT["reel_minutes"] = round(F.duration(out_path) / 60, 2)
    data.update({"animal": "chat", "topic": topics[0]})
    return data


def build_long(history, out_path):
    data, chats, topics = write_chats(history, 5, 16)
    parts = []
    for i, c in enumerate(chats):
        job = os.path.join(F.WORK, f"chat_long_{i}")
        shutil.rmtree(job, ignore_errors=True)
        parts.append(render_chat(c, job, 1920, 1080))
        F.log(f"chat {i + 1}/{len(chats)} ready")
    lst = os.path.join(F.WORK, "chat_long_list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    F.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
           "-movflags", "+faststart", out_path])
    F.REPORT["long_minutes"] = round(F.duration(out_path) / 60, 2)
    data.update({"animal": "chat", "topic": ", ".join(topics)})
    return data
