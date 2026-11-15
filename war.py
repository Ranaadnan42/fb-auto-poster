"""
Battles Untold - WAR HISTORY AGENT (Facebook page).

Har jang ki kahani: kab hui, kyun hui (wajah), kahan, kis ke beech, kaun jeeta, kaun haara, kitne log mare,
aur dunya par us ka asar. Sab se pehli jang (Sumer, ~2500 BC) se shuru ho kar aaj tak - kabhi khatam nahi:
seed list khatam ho to agent khud agli jang dhoondta hai.

MODE=reel  -> 9:16, ~60-75 sec, ek jang ka poora khulasa (kab/kyun/kaun jeeta/kitne mare) + page story
MODE=long  -> 16:9, ~5-6 min documentary, "History of Every War" series - pehli jang se tarteeb se
MODE=brand -> ek dafa: page ki profile + cover picture

Agent kaam:
  - Wikipedia se asal facts (tareekh, nateeja, casualties) - AI sirf inhi facts se script likhta hai
  - Har jumle par wohi footage jo bola ja raha hai: 1900+ jangon ki asli archive newsreel (Internet Archive /
    Commons, public domain), purani jangon ki asli paintings / naqshe / qile / maidan-e-jang aaj -
    har clip AI (footage_agent) dekh kar pass karta hai, gore / ghalat zamana / doosri jang rad
  - trend_scout: log aaj kal kya dekh rahe hain - us hisaab se angle
Env: WAR_PAGE_ID, WAR_PAGE_TOKEN, WAR_GEMINI_API_KEY (na ho to GEMINI_API_KEY), GROQ_API_KEY, PIXABAY_API_KEY,
     MODE, POST_AT, DRY_RUN
"""
import datetime
import json
import os
import random
import re
import sys
import time

MODE = (os.environ.get("MODE") or "reel").strip().lower()
os.environ["KIND"] = "reel" if MODE == "reel" else "long"
os.environ["LANGUAGE"] = "en"
os.environ["FOOTAGE_WAR"] = "1"
os.environ.setdefault("NEWS_BUDGET_MIN", "55" if MODE == "reel" else "150")

import requests  # noqa: E402

import footage  # noqa: E402
import news  # noqa: E402
import news_video as nv  # noqa: E402

PAGE = "war"
PAGE_NAME = "Battles Untold"
GRAPH_VER = "v23.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VER}"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
HIST_FILE = "war_history.json"
REPORT_FILE = f"war_{MODE}_last_run.json"
OUT_FILE = "final_war.mp4"
UA = {"User-Agent": "BattlesUntoldBot/1.0 (https://github.com/Ranaadnan42/fb-auto-poster)"}

news.CURRENT_PAGE = PAGE
news.PAGES[PAGE] = {"name": PAGE_NAME, "token": (os.environ.get("WAR_PAGE_TOKEN") or "").strip(),
                    "id": (os.environ.get("WAR_PAGE_ID") or "").strip(), "color": "&H00103C8C", "accent": "0x8C3C10"}
log = news.log
REPORT = {"time_utc": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "mode": MODE, "dry_run": DRY_RUN,
          "errors": []}

# Pehli jang se tarteeb se (English Wikipedia titles). Khatam ho jaye to agent khud agli dhoondta hai.
WARS = [
    "Lagash–Umma border conflict", "Battle of Megiddo (15th century BC)", "Battle of Kadesh",
    "Siege of Lachish", "Battle of Marathon", "Battle of Thermopylae", "Battle of Salamis",
    "Peloponnesian War", "Battle of Gaugamela", "Battle of the Hydaspes", "Kalinga War",
    "First Punic War", "Battle of Cannae", "Battle of Zama", "Gallic Wars", "Battle of Alesia",
    "Battle of Actium", "Battle of the Teutoburg Forest", "Siege of Jerusalem (70 CE)", "Battle of Adrianople",
    "Battle of the Catalaunian Plains", "Battle of Badr", "Battle of Uhud", "Battle of the Trench",
    "Battle of Yarmuk", "Battle of al-Qadisiyyah", "Battle of Tours", "Battle of Talas",
    "Battle of Manzikert", "Battle of Hastings", "First Crusade", "Battle of Hattin", "Third Crusade",
    "Mongol invasion of the Khwarazmian Empire", "Siege of Baghdad (1258)", "Battle of Ain Jalut",
    "Battle of Bannockburn", "Hundred Years' War", "Battle of Crécy", "Battle of Agincourt",
    "Battle of Ankara", "Fall of Constantinople", "Wars of the Roses", "Battle of Bosworth Field",
    "Battle of Chaldiran", "Battle of Mohács", "First Battle of Panipat", "Second Battle of Panipat",
    "Spanish conquest of the Aztec Empire", "Spanish conquest of the Inca Empire", "Spanish Armada",
    "Imjin War", "Battle of Sekigahara", "Thirty Years' War", "English Civil War", "Battle of Vienna",
    "Great Northern War", "Battle of Poltava", "War of the Spanish Succession", "Battle of Karnal",
    "Third Battle of Panipat", "Battle of Plassey", "Seven Years' War", "American Revolutionary War",
    "Battle of Saratoga", "Siege of Yorktown", "French Revolutionary Wars", "Battle of the Nile",
    "Battle of Trafalgar", "Battle of Austerlitz", "French invasion of Russia", "Battle of Waterloo",
    "War of 1812", "Greek War of Independence", "First Anglo-Afghan War", "First Opium War",
    "Mexican–American War", "Crimean War", "Indian Rebellion of 1857", "American Civil War",
    "Battle of Gettysburg", "Paraguayan War", "Franco-Prussian War", "Anglo-Zulu War",
    "Battle of Little Bighorn", "First Sino-Japanese War", "Spanish–American War", "Second Boer War",
    "Boxer Rebellion", "Russo-Japanese War", "Balkan Wars", "World War I", "Gallipoli campaign",
    "Battle of Verdun", "Battle of the Somme", "Battle of Jutland", "Battle of Passchendaele",
    "Russian Civil War", "Polish–Soviet War", "Turkish War of Independence", "Chaco War",
    "Second Italo-Ethiopian War", "Spanish Civil War", "Second Sino-Japanese War", "World War II",
    "Invasion of Poland", "Winter War", "Battle of France", "Dunkirk evacuation", "Battle of Britain",
    "Operation Barbarossa", "Siege of Leningrad", "Attack on Pearl Harbor", "Battle of Midway",
    "Second Battle of El Alamein", "Battle of Stalingrad", "Battle of Kursk", "Battle of Guadalcanal",
    "Normandy landings", "Battle of Leyte Gulf", "Battle of the Bulge", "Battle of Iwo Jima",
    "Battle of Okinawa", "Battle of Berlin", "Atomic bombings of Hiroshima and Nagasaki",
    "Chinese Civil War", "Indo-Pakistani war of 1947–1948", "1948 Arab–Israeli War", "Korean War",
    "Battle of Inchon", "First Indochina War", "Battle of Dien Bien Phu", "Algerian War", "Suez Crisis",
    "Bay of Pigs Invasion", "Sino-Indian War", "Indo-Pakistani war of 1965", "Vietnam War",
    "Tet Offensive", "Six-Day War", "Nigerian Civil War", "Football War", "Indo-Pakistani war of 1971",
    "Yom Kippur War", "Soviet–Afghan War", "Iran–Iraq War", "Falklands War", "Gulf War", "Bosnian War",
    "First Chechen War", "Kargil War", "Kosovo War", "War in Afghanistan (2001–2021)", "Iraq War",
]
# Reels pehle in mash-hoor jangon par (zyada views), phir baqi sab
FAMOUS = ["World War II", "World War I", "Battle of Stalingrad", "Normandy landings", "Battle of Thermopylae",
          "Battle of Waterloo", "Attack on Pearl Harbor", "Battle of Hastings", "Battle of Gettysburg",
          "Vietnam War", "Battle of Midway", "Battle of Cannae", "Fall of Constantinople", "Battle of Britain",
          "Battle of the Bulge", "Korean War", "Battle of Agincourt", "Battle of Gaugamela", "Battle of Iwo Jima",
          "Spanish Armada", "Battle of Trafalgar", "Battle of Berlin", "Gulf War", "Battle of Badr",
          "Battle of Yarmuk", "Lagash–Umma border conflict", "Battle of Megiddo (15th century BC)"]


# ---------------------------------------------------------------- history
def load_hist():
    try:
        with open(HIST_FILE, encoding="utf-8") as f:
            h = json.load(f)
    except Exception:
        h = {}
    for k in ("reel", "long", "used_clips", "extra"):
        h.setdefault(k, [])
    return h


def save_hist(h):
    h["used_clips"] = h["used_clips"][-3000:]
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def done_titles(h, mode):
    return {x["war"] for x in h[mode]}


def next_from_ai(h, after):
    """Seed list khatam: agent khud agli (chronological) jang dhoondta hai jo pehle nahi aayi."""
    seen = sorted(done_titles(h, "reel") | done_titles(h, "long") | set(h["extra"]))
    j = news.ask_json(f"""You run a war-history page that tells the story of EVERY war and major battle in history,
in chronological order. The last one covered was "{after}". Already covered (never repeat): {json.dumps(seen[-250:])}
Suggest the next 8 real wars or major battles (any continent, any era - especially ones not yet covered, including
Asian, African and Latin American ones), each as its exact English Wikipedia article title. Avoid wars that are
still being fought today. Return JSON {{"wars": ["..."]}}""")
    out = [w.strip() for w in (j.get("wars") or []) if isinstance(w, str) and w.strip() and w.strip() not in seen]
    h["extra"] += out
    return out


def pick_war(h):
    if MODE == "long":                          # series: pehli jang se tarteeb se
        done = done_titles(h, "long")
        for w in WARS + h["extra"]:
            if w not in done:
                return w, len(done) + 1
        last = h["long"][-1]["war"] if h["long"] else WARS[-1]
        for w in next_from_ai(h, last):
            return w, len(done) + 1
        raise RuntimeError("agli jang nahi mili")
    done = done_titles(h, "reel")
    pool = [w for w in FAMOUS if w not in done] or [w for w in WARS + h["extra"] if w not in done]
    if not pool:
        pool = next_from_ai(h, h["reel"][-1]["war"] if h["reel"] else WARS[-1])
    return random.choice(pool[:6]), None


# ---------------------------------------------------------------- facts (Wikipedia)
def _wiki(params):
    params.update({"format": "json", "formatversion": 2})
    for i in range(3):
        try:
            return requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=UA, timeout=40).json()
        except Exception as e:
            log(f"wiki retry {i + 1}: {str(e)[:100]}")
            time.sleep(4)
    return {}


def _clean_wiki(v):
    v = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", v, flags=re.S)
    v = re.sub(r"\{\{(?:flag(?:icon|country|deco)?|flagcountry)\|([^|}]+)[^}]*\}\}", r"\1", v, flags=re.I)
    v = re.sub(r"\{\{(?:nowrap|small|lang\|[a-z]+)\|([^{}]*)\}\}", r"\1", v, flags=re.I)
    v = re.sub(r"\{\{[^{}]*\}\}", "", v)
    v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"<br\s*/?>", "; ", v)
    v = re.sub(r"<[^>]+>|'''?|&nbsp;", " ", v)
    return re.sub(r"\s{2,}", " ", v).strip(" ;,")


def gather_facts(title):
    j = _wiki({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title})
    pages = (j.get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing"):
        s = _wiki({"action": "query", "list": "search", "srsearch": title, "srlimit": 1})
        hits = (s.get("query") or {}).get("search") or []
        if not hits:
            raise RuntimeError(f"Wikipedia par '{title}' nahi mila")
        title = hits[0]["title"]
        j = _wiki({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title})
        pages = (j.get("query") or {}).get("pages") or []
    page = pages[0]
    title = page.get("title", title)
    text = page.get("extract") or ""
    text = re.split(r"\n==\s*(See also|References|Notes|Further reading|External links|Citations|Sources)\s*==",
                    text)[0]
    box = {}
    w = _wiki({"action": "parse", "page": title, "prop": "wikitext", "section": 0, "redirects": 1})
    wt = ((w.get("parse") or {}).get("wikitext")) or ""
    for key in ("date", "place", "location", "result", "territory", "combatant1", "combatant2", "combatant3",
                "commander1", "commander2", "strength1", "strength2", "casualties1", "casualties2", "casualties3"):
        m = re.search(rf"\|\s*{key}\s*=(.*?)(?=\n\s*\|\s*[a-z_0-9]+\s*=|\n\}}\}})", wt, flags=re.S | re.I)
        if m:
            v = _clean_wiki(m.group(1))[:500]
            if v:
                box[key] = v
    if len(text) < 400:
        raise RuntimeError(f"'{title}' ke facts kam hain")
    return {"title": title, "infobox": box, "text": text[:14000 if MODE == "long" else 7000]}


def year_of(facts):
    d = facts["infobox"].get("date", "") + " " + facts["text"][:600]
    bc = re.search(r"(\d{3,4})\s*(BC|BCE)", d)
    if bc:
        return -int(bc.group(1))
    m = re.search(r"\b(1\d{3}|20\d{2}|[1-9]\d{2})\b", d)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- script
def write_script(facts, episode):
    yr = year_of(facts)
    era = ("film era - for visuals prefer real archive newsreel footage, e.g. '<war name> newsreel', "
           "'<battle> 1944 archive footage', '<country> soldiers 1917 film', plus maps, memorials and the "
           "real place" if yr and yr >= 1900 else
           "pre-film era - for visuals use historical PAINTINGS/engravings of this battle, maps, museum weapons and "
           "armour of that era, castles/forts/ruins and the real battlefield or city today. Never modern weapons")
    trends = ""
    try:
        import trend_scout
        trends = trend_scout.text("war")
    except Exception:
        pass
    if MODE == "reel":
        shape = """a vertical REEL of 160-200 spoken words (60-75 seconds) in 7-9 scenes, in this order:
  1) a scroll-stopping hook (a shocking true number or twist from the facts), 2) WHEN and WHERE, 3) WHY it started,
  4-6) how it unfolded / the turning point, 7) WHO WON and WHO LOST, 8) how many people died (as the facts say),
  9) what it changed + "Follow Battles Untold for the story of every war in history." """
        series = ""
    else:
        shape = """a LONG documentary of 800-950 spoken words (5-6 minutes) in 26-34 scenes, with these chapters
  (put the chapter name in each scene's "label"): "THE HOOK", "BEFORE THE WAR", "WHY IT STARTED", "THE SIDES",
  "HOW IT UNFOLDED", "THE TURNING POINT", "WHO WON", "THE HUMAN COST", "WHAT IT CHANGED". End with: this was
  episode N of History of Every War, follow Battles Untold, like and share, comment which war we should cover next."""
        series = f'\nThis is EPISODE {episode} of the series "History of Every War - from the first war to today".'
    prompt = f"""You are the narrator and writer of the Facebook page "Battles Untold" (war history for viewers in the
USA, UK, Europe, Canada, Australia and the Gulf). Write {shape}{series}
Subject: {facts['title']}
INFOBOX: {json.dumps(facts['infobox'], ensure_ascii=False)}
WIKIPEDIA TEXT:
{facts['text']}

Rules:
- Natural spoken English like a great History Channel narrator; your OWN words, never copied sentences.
- ONLY facts written above. Dates, winners/losers and death tolls exactly as written (keep "estimated", "about",
  ranges). If the outcome was disputed or inconclusive, say so. If no casualty number is given, don't invent one.
- If this was "the first recorded war/battle in history" (or similar) and the text says so, say it clearly.
- Strictly neutral: never praise or blame a nation, religion or ethnic group; no glorifying killing; no graphic or
  gory descriptions (Facebook monetization). Explain causes and consequences like a historian.
- ORIGINALITY: add 1-2 lines of your own historian insight (why it still matters today) - clearly as analysis.
- Era: {era}.
- For EVERY scene give "visuals": 1-3 short ENGLISH search terms, in the order the narration mentions them, naming
  the SPECIFIC thing said (the battle, the place, the commander, the ships, the trenches, the map, the fort...).
  Never generic mood shots (fire, smoke, sunset, sky, random soldiers of another era), never gore.
- "subjects": 2-5 real names from the text as exact English Wikipedia titles (the battle/war itself, commanders,
  key places, ships) - their real portraits/paintings are shown.
{trends}
Return JSON:
{{"title": "Facebook video title, max 12 words, curiosity hook + the war name",
  "years": "on-screen years e.g. '1939-1945' or '1274 BC'",
  "subjects": ["..."],
  "summary": {{"when": "...", "where": "...", "why": "max 12 words", "winner": "...", "loser": "...", "deaths": "as written, or 'unknown'"}},
  "scenes": [{{"label": "short on-screen label, max 4 words, e.g. WHY IT STARTED", "text": "...", "visuals": ["..."]}}],
  "caption": "2-3 sentence post description"}}"""
    j = news.ask_json(prompt)
    sc = [s for s in (j.get("scenes") or []) if str(s.get("text") or "").strip()]
    words = sum(len(s["text"].split()) for s in sc)
    need = 140 if MODE == "reel" else 700
    if len(sc) < 5 or words < need:
        log(f"script chhota ({words} lafz) - dobara likhwa rahe hain")
        j2 = news.ask_json(prompt + f"\nIMPORTANT: your last answer was too short ({words} words). "
                                    f"Write at least {need + 60} spoken words.")
        sc2 = [s for s in (j2.get("scenes") or []) if str(s.get("text") or "").strip()]
        if sum(len(s["text"].split()) for s in sc2) > words:
            j, sc = j2, sc2
    if len(sc) < 4:
        raise RuntimeError("AI ne script nahi di")
    j["scenes"] = sc
    return j


# ---------------------------------------------------------------- video
def build_video(script, facts, used):
    badge = (script.get("years") or "").strip() or "WAR HISTORY"
    subj = [x.strip() for x in (script.get("subjects") or []) if isinstance(x, str) and x.strip()][:5]
    if facts["title"] not in subj:
        subj.insert(0, facts["title"])
    fallback = [f"@{x}" for x in subj] + [f"{facts['title']} painting", f"{facts['title']} map",
                                          f"{facts['title']} memorial"]
    nv.STORY_CLIPS.clear()
    scenes = []
    for i, sc in enumerate(script["scenes"]):
        terms = [t for t in (sc.get("visuals") or []) if isinstance(t, str) and t.strip()]
        if i < len(subj) and (i == 0 or random.random() < 0.5):
            terms = [f"@{subj[i]}"] + terms           # asli painting/portrait/naqsha
        label = str(sc.get("label") or "").strip().upper()[:40] or None
        try:
            scenes.append(nv.build_scene(i, PAGE, sc["text"], terms, label, badge, used, fallback))
        except Exception as e:
            log(f"scene {i} fail: {str(e)[:200]}")
            REPORT["errors"].append(f"scene {i}: {str(e)[:150]}")
    if len(scenes) < max(3, len(script["scenes"]) // 2):
        raise RuntimeError("bohat se scenes nahi banay")
    lst = os.path.join(nv.WORK, "all.txt")
    with open(lst, "w") as f:
        f.write("".join(f"file '{os.path.abspath(p)}'\n" for p in scenes))
    joined = os.path.join(nv.WORK, "joined.mp4")
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    total = nv.duration(joined)
    music = os.path.join(nv.WORK, "music.wav")
    dark_music(music, total)
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", music, "-filter_complex",
            f"[1:a]volume=0.25,afade=t=in:d=2,afade=t=out:st={max(0, total - 3):.2f}:d=3[m];"
            "[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            OUT_FILE])
    log(f"video ban gayi: {total:.0f}s, {len(scenes)} scenes")
    return OUT_FILE


def dark_music(path, secs):
    """Halka, sanjeeda documentary drone + aahista dhol (koi copyright nahi - khud bana)."""
    root = random.choice([55.0, 61.7, 65.4])
    parts = [f"0.05*sin(2*PI*{root * m:.2f}*t)*(0.6+0.4*sin(2*PI*t/{p}))"
             for m, p in ((1, 14), (1.5, 11), (2, 17), (2.38, 9))]
    parts.append("0.07*sin(2*PI*48*t)*exp(-8*mod(t,1.6))")             # dheemi jang ki dhadkan
    nv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
            f"aevalsrc='{'+'.join(parts)}':s=44100:d={secs + 1:.1f}", "-af", "lowpass=f=1400,volume=0.9", path])


# ---------------------------------------------------------------- Facebook
def page():
    P = dict(news.PAGES[PAGE])
    if P["id"] and P["token"]:
        import fbtoken
        P["token"] = fbtoken.page_token(P["id"], P["token"])      # user token ho to never-expiring page token
    return P


def description(script, facts):
    import seo
    s = script.get("summary") or {}
    lines = [f"📅 When: {s.get('when')}", f"📍 Where: {s.get('where')}", f"⚔️ Why: {s.get('why')}",
             f"🏆 Winner: {s.get('winner')}", f"🏳️ Lost: {s.get('loser')}", f"🕯️ Deaths: {s.get('deaths')}"]
    card = "\n".join(x for x in lines if not x.endswith(": None") and not x.endswith(": "))
    said = " ".join(sc.get("text", "") for sc in script["scenes"])
    src = f"📚 Source: Wikipedia - {facts['title']}"
    try:
        cap = seo.build(news.ask_json, PAGE, script.get("title") or facts["title"], said, "en",
                        is_reel=MODE == "reel")
        parts = cap.split("\n\n")
        parts[1:1] = [card, src]
        out = "\n\n".join(p for p in parts if p)
        return out + (" #reels" if MODE == "reel" and "#reels" not in out.lower() else "")
    except Exception as e:
        log(f"SEO fail ({str(e)[:100]})")
    return f"⚔️ {script.get('title')}\n\n{card}\n\n{script.get('caption', '')}\n\n{src}\n\n#BattlesUntold #history #war"


def brand():
    """Ek dafa: page ki profile + cover picture (asli public-domain jang ki painting)."""
    from PIL import Image, ImageDraw, ImageFont
    P = page()
    img = os.path.join(nv.WORK, "brand_src.jpg")
    got = None
    for name in ("Battle of Waterloo", "Battle of Trafalgar", "Battle of Hastings", "Battle of Gettysburg"):
        got = footage.real_photo(name, img, [], min_w=1200)
        if got:
            break
    if not got:
        raise RuntimeError("brand ki tasveer nahi mili")
    im = Image.open(img).convert("RGB")
    w, h = im.size
    cw, ch = (w, int(w / 1.777)) if w / h < 1.777 else (int(h * 1.777), h)
    cov = im.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2)).resize((1920, 1080))
    dark = Image.new("RGB", cov.size, (0, 0, 0))
    cov = Image.blend(cov, dark, 0.35)
    d = ImageDraw.Draw(cov)
    try:
        f1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 130)
        f2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 46)
    except Exception:
        f1 = f2 = ImageFont.load_default()
    for txt, f, y in (("BATTLES UNTOLD", f1, 400), ("The story of every war in history", f2, 580)):
        tw = d.textlength(txt, font=f)
        d.text(((1920 - tw) / 2, y), txt, font=f, fill=(235, 215, 170), stroke_width=4, stroke_fill=(0, 0, 0))
    cov_path = os.path.join(nv.WORK, "cover.jpg")
    cov.save(cov_path, quality=94)
    s = min(w, h)
    prof = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((1080, 1080))
    prof = Image.blend(prof, Image.new("RGB", prof.size, (0, 0, 0)), 0.45)
    d = ImageDraw.Draw(prof)
    try:
        f3 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 210)
    except Exception:
        f3 = ImageFont.load_default()
    for txt, y in (("BATTLES", 300), ("UNTOLD", 560)):
        tw = d.textlength(txt, font=f3)
        d.text(((1080 - tw) / 2, y), txt, font=f3, fill=(235, 215, 170), stroke_width=6, stroke_fill=(0, 0, 0))
    prof_path = os.path.join(nv.WORK, "profile.jpg")
    prof.save(prof_path, quality=94)
    import shutil
    shutil.copy(prof_path, "final_war_profile.jpg")
    shutil.copy(cov_path, "final_war_cover.jpg")
    if DRY_RUN:
        log("brand: dry run - sirf tasveerein")
        return
    with open(prof_path, "rb") as f:
        r = requests.post(f"{GRAPH}/{P['id']}/picture", files={"source": f},
                          data={"access_token": P["token"]}, timeout=120)
    log(f"profile picture: {r.status_code} {r.text[:200]}")
    with open(cov_path, "rb") as f:
        cid = nv.fb_json(requests.post(f"{GRAPH}/{P['id']}/photos", timeout=300, files={"source": f}, data={
            "caption": "Welcome to Battles Untold ⚔️ The true story of every war in history - from the very first "
                       "recorded war 4,500 years ago to modern times. When it happened, why it started, who won, who "
                       "lost and what it cost. New videos every day.\n\n#BattlesUntold #History #WarHistory",
            "access_token": P["token"]}))["id"]
    r = requests.post(f"{GRAPH}/{P['id']}", timeout=120,
                      data={"cover": cid, "no_feed_story": "true", "access_token": P["token"]})
    log(f"cover: {r.status_code} {r.text[:200]}")


# ---------------------------------------------------------------- main
def main():
    os.makedirs(nv.WORK, exist_ok=True)
    if MODE == "brand":
        brand()
        return
    P = page()
    if not DRY_RUN and not (P["id"] and P["token"]):
        log("WAR_PAGE_ID / WAR_PAGE_TOKEN abhi set nahi - page jurne tak kuch nahi")
        REPORT["waiting"] = "page secrets missing"
        return
    h = load_hist()
    war, episode = pick_war(h)
    log(f"Jang: {war} (episode {episode})")
    try:
        facts = gather_facts(war)
    except Exception as e:
        log(f"facts fail ({e}) - doosri jang")
        h["extra"] = [x for x in h["extra"] if x != war]
        h[MODE].append({"war": war, "date": REPORT["time_utc"], "skipped": str(e)[:100]})
        save_hist(h)
        war, episode = pick_war(h)
        facts = gather_facts(war)
    script = write_script(facts, episode)
    log(f"Title: {script.get('title')} | {len(script['scenes'])} scenes")
    if MODE == "long" and episode:
        script["title"] = f"{script.get('title') or facts['title']} | History of Every War Ep. {episode}"
    path = build_video(script, facts, h["used_clips"])
    REPORT.update({k: v for k, v in nv.REPORT.items() if k not in ("errors", "posted")})
    desc = description(script, facts)
    log(f"--- description ---\n{desc}\n")
    meta = {"war": war, "wiki": facts["title"], "date": REPORT["time_utc"], "title": script.get("title", "")[:150],
            "episode": episode, "dur": round(nv.duration(path))}
    if not DRY_RUN:
        import slot_wait
        slot_wait.wait(log)
        meta["post_id"] = nv.post_reel(P, path, desc) if MODE == "reel" else \
            nv.post_long(P, path, script.get("title") or facts["title"], desc)
        log(f"posted {meta['post_id']}")
        news.POSTS_LOG = "war_posts_history.json"
        news.log_post(PAGE, meta["post_id"], MODE, [war], meta["title"])
    h[MODE].append(meta)
    save_hist(h)
    REPORT["posted"] = meta


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        REPORT["errors"].append(f"fatal: {str(e)[:300]}")
        raise
    finally:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(REPORT, f, ensure_ascii=False, indent=1, default=str)
    if REPORT["errors"] and not REPORT.get("posted") and not DRY_RUN and MODE != "brand":
        sys.exit(1)
