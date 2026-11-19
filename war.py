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
    Commons, public domain) aur har jang ki ASLI JAGAH aaj (maidan-e-jang, qila, shehar, yaadgaar) - TASVEER KABHI NAHI -
    har clip AI (footage_agent) dekh kar pass karta hai, gore / ghalat zamana / doosri jang rad
  - trend_scout: log aaj kal kya dekh rahe hain - us hisaab se angle
Env: WAR_PAGE_ID, WAR_PAGE_TOKEN, WAR_GEMINI_API_KEY (na ho to GEMINI_API_KEY), GROQ_API_KEY, PIXABAY_API_KEY,
     MODE, POST_AT, DRY_RUN
"""
try:  # Gemma 4 fallback (free 14,400/din) ke liye Gemini requests theek karta hai - gemfix.py
    import sys as _gf_sys, os as _gf_os
    _gf_dir = _gf_os.path.dirname(_gf_os.path.abspath(__file__))
    _gf_sys.path[:0] = [p for p in (_gf_dir, _gf_os.path.dirname(_gf_dir)) if p not in _gf_sys.path]
    import gemfix  # noqa: F401,E402
except Exception:
    pass
import datetime
import json
import os
import random
import re
import sys
import time

MODE = (os.environ.get("MODE") or "reel").strip().lower()
os.environ["KIND"] = "long" if MODE == "long" else "reel"
os.environ["LANGUAGE"] = "en"
os.environ["FOOTAGE_WAR"] = "1"
os.environ["NO_PHOTOS"] = "1"
os.environ["NO_REUSE"] = "1"           # jo bola ja raha hai wohi - pichli clip dobara nahi (warna text card)          # malik: reel aur long dono mein tasveer nahi - sirf asli video, asli jagahein
os.environ.setdefault("NEWS_BUDGET_MIN", "55" if MODE == "reel" else "150")

import requests  # noqa: E402

import content_rules  # noqa: E402
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
# 1) Dunya ki pehli jang se tarteeb se purane daur ki jangein
ANCIENT = ['Prehistoric warfare', 'Jebel Sahaba', 'Nataruk', 'Talheim Death Pit', 'Lagash–Umma border conflict', 'Sargon of Akkad', 'Battle of Megiddo (15th century BC)', 'Battle of the Ten Kings', 'Battle of Kadesh', 'Trojan War', 'Battle of Muye', 'Battle of Djahy', 'Siege of Lachish', 'Battle of Marathon', 'Battle of Thermopylae', 'Battle of Salamis', 'Peloponnesian War', 'Kalinga War']
# 2) Phir saltanatein: Persian, Roman, Arab (tarteeb se)
EMPIRES = ['Fall of Babylon', 'Battle of Opis', 'Battle of Pelusium (525 BC)', 'Greco-Persian Wars', 'Battle of Issus', 'Battle of Gaugamela', 'Samnite Wars', 'Pyrrhic War', 'First Punic War', 'Second Punic War', 'Battle of Cannae', 'Battle of Zama', 'Macedonian Wars', 'Third Punic War', 'Mithridatic Wars', 'Gallic Wars', 'Battle of Alesia', 'Battle of Carrhae', "Caesar's civil war", 'Battle of Pharsalus', 'Battle of Philippi', 'Battle of Actium', 'Battle of the Teutoburg Forest', 'Roman conquest of Britain', "Boudica's uprising", 'Roman–Parthian Wars', 'Siege of Jerusalem (70 CE)', 'Bar Kokhba revolt', 'Roman–Persian Wars', 'Battle of Edessa', 'Battle of the Milvian Bridge', 'Battle of Adrianople', 'Sack of Rome (410)', 'Battle of the Catalaunian Plains', 'Fall of the Western Roman Empire', 'Gothic War (535–554)', 'Byzantine–Sasanian War of 602–628', 'Battle of Dhi Qar', 'Battle of Badr', 'Battle of Uhud', 'Battle of the Trench', 'Conquest of Mecca', 'Ridda wars', 'Battle of Yarmuk', 'Muslim conquest of the Levant', 'Battle of al-Qadisiyyah', 'Muslim conquest of Persia', 'Battle of Nahavand', 'Muslim conquest of Egypt', 'Battle of the Camel', 'Battle of Siffin', 'Battle of Karbala', 'Siege of Constantinople (674–678)', 'Umayyad conquest of Hispania', 'Battle of Guadalete', 'Siege of Constantinople (717–718)', 'Battle of Tours', 'Battle of the Zab', 'Battle of Talas', 'Byzantine–Arab wars']
# malik ka faisla: sirf woh jangein jin ki ASLI film maujood hai - pehli filmi jang (1897) se aaj tak, tarteeb se
FILM_WARS = [
    "Greco-Turkish War (1897)", "Spanish–American War", "Philippine–American War", "Second Boer War",
    "Boxer Rebellion", "Russo-Japanese War", "Mexican Revolution", "Italo-Turkish War", "First Balkan War",
    "Second Balkan War", "World War I", "Gallipoli campaign", "Battle of the Somme", "Battle of Verdun",
    "Russian Civil War", "Polish–Soviet War", "Greco-Turkish War (1919–1922)", "Irish War of Independence",
    "Rif War", "Chinese Civil War", "Chaco War", "Second Italo-Ethiopian War", "Spanish Civil War",
    "Second Sino-Japanese War", "Winter War", "World War II", "Battle of Britain", "Attack on Pearl Harbor",
    "Battle of Stalingrad", "Battle of Midway", "Normandy landings", "Battle of Iwo Jima", "Battle of Berlin",
    "Indo-Pakistani war of 1947–1948", "1948 Arab–Israeli War", "Korean War", "First Indochina War",
    "Algerian War", "Suez Crisis", "Vietnam War", "Indo-Pakistani war of 1965", "Six-Day War",
    "Indo-Pakistani war of 1971", "Yom Kippur War", "Soviet–Afghan War", "Iran–Iraq War", "Falklands War",
    "Gulf War", "Bosnian War", "First Chechen War", "Kosovo War", "Kargil War", "War in Afghanistan (2001–2021)",
    "Iraq War",
]
WARS = []          # malik: seedha mulk-ba-mulk (har mulk ki pehli filmi jang se), FILM_WARS ab istemal nahi

# 3) Phir mulk-ba-mulk: har mulk ki ahem jangein (us mulk ke andar purani se nayi), phir agla mulk
COUNTRIES = [
    "United States", "United Kingdom", "Canada", "New Zealand", "Austria", "Australia", "Germany", "France",
    "Ireland", "China", "India", "Egypt", "Iran", "Greece", "Italy", "Turkey", "Iraq", "Syria", "Mongolia",
    "Japan", "Korea", "Vietnam", "Spain", "Portugal", "Russia", "Poland", "Sweden", "Norway", "Denmark",
    "Netherlands", "Belgium", "Hungary", "Serbia", "Bulgaria", "Romania", "Ukraine", "Finland", "Scotland",
    "Switzerland", "Czech Republic", "Croatia", "Bosnia and Herzegovina", "Albania", "Georgia", "Armenia",
    "Azerbaijan", "Pakistan", "Afghanistan", "Bangladesh", "Sri Lanka", "Nepal", "Myanmar", "Thailand",
    "Cambodia", "Indonesia", "Philippines", "Malaysia", "Kazakhstan", "Uzbekistan", "Saudi Arabia", "Yemen",
    "Oman", "Kuwait", "Jordan", "Lebanon", "Israel", "Palestine", "Libya", "Tunisia", "Algeria", "Morocco",
    "Sudan", "Ethiopia", "Somalia", "Kenya", "Uganda", "Rwanda", "Congo", "Angola", "Mozambique", "Zimbabwe",
    "South Africa", "Nigeria", "Ghana", "Mali", "Senegal", "Madagascar", "Mexico", "Cuba", "Haiti",
    "Guatemala", "Nicaragua", "Colombia", "Venezuela", "Peru", "Bolivia", "Chile", "Argentina", "Paraguay",
    "Brazil", "Uruguay", "Ecuador", "Taiwan", "Tibet", "Laos", "Estonia", "Latvia", "Lithuania", "Belarus",
    "Cyprus", "Iceland",
]
PER_COUNTRY = 12
FILM_YEAR = 1897   # is se pehle ki jangon mein asli film nahi - us daur ki ASLI tasveerein (Commons)
H_COUNTRY_N = [1]       # ek mulk ki zyada se zyada itni jangein, phir agla mulk


# ---------------------------------------------------------------- history
def load_hist():
    try:
        with open(HIST_FILE, encoding="utf-8") as f:
            h = json.load(f)
    except Exception:
        h = {}
    h.setdefault("country_i", 0)
    h.setdefault("country_n", 0)
    for k in ("reel", "long", "used_clips", "extra"):
        h.setdefault(k, [])
    return h


def save_hist(h):
    h["used_clips"] = h["used_clips"][-3000:]
    with open(HIST_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=1)


def _norm(t):
    return re.sub(r"[\u2010-\u2015-]", "-", str(t or "")).strip().lower()


def done_titles(h, mode):
    return {x["war"] for x in h[mode]} | {x.get("wiki") for x in h[mode] if x.get("wiki")}


def film_count(war):
    """Is jang ki ASLI battle film kitni maujood hai (Internet Archive newsreels + Commons videos).
    Jis jang ki film hi nahi us par 'battles' video nahi ban sakti - wo jang chhor do."""
    name = re.sub(r"\s*\(.*?\)", "", war).replace("\u2013", "-").strip()
    n = footage.war_film_count(name)
    try:
        n += len(footage.commons(f"{name} footage", True))
    except Exception:
        pass
    return n


MIN_FILM = 5      # kam az kam itni asli film/newsreel - warna jang skip


def country_war(h, done):
    """Mulk-ba-mulk: mojooda mulk ki agli BARI jang jis ki ASLI battle film maujood ho (1897 ke baad),
    us mulk ki tareekh mein tarteeb se. Choti/gumnaam jangein jin ki footage nahi - skip."""
    skip = set(h.setdefault("no_film", []))
    for _ in range(len(COUNTRIES)):
        c = COUNTRIES[h["country_i"] % len(COUNTRIES)]
        if h["country_n"] < PER_COUNTRY:
            j = news.ask_json(f"""For the Facebook page "Battles Untold" (real battle footage of every country's wars):
list the BIG, well-known wars and major battles fought by {c} from {FILM_YEAR} onward that were FILMED - real
newsreel / archive combat film of them exists (e.g. World War I, World War II battles, Korean War, Vietnam War,
Gulf War). OLDEST FIRST, not still ongoing. NO small frontier skirmishes, uprisings or local conflicts without film.
Never these (already covered): {json.dumps(sorted(done | skip)[-300:])}
Return JSON {{"wars": ["up to 12 exact English Wikipedia article titles, in chronological order"]}}""")
            for w in j.get("wars") or []:
                w = w.strip() if isinstance(w, str) else ""
                if not w or _norm(w) in {_norm(x) for x in done | skip}:
                    continue
                n = film_count(w)
                if n < MIN_FILM:
                    log(f"  '{w}': asli battle film sirf {n} - skip")
                    h["no_film"].append(w)
                    skip.add(w)
                    continue
                h["country_n"] += 1
                H_COUNTRY_N[0] = h["country_n"]
                REPORT["country"] = c
                log(f"Mulk: {c} ({h['country_n']}/{PER_COUNTRY}) - '{w}' ki {n} asli film")
                return w
        h["country_i"] += 1                      # is mulk ki jangein mukammal - agla mulk
        h["country_n"] = 0
    return None


def pick_war(h):
    """Tarteeb: 1) dunya ki pehli jang se purane daur ki jangein, 2) Persian / Roman / Arab saltanatein,
    3) phir mulk-ba-mulk. Reel aur long dono agli jang lete hain - har jang ek dafa, koi chhoot-ti nahi."""
    done = done_titles(h, "reel") | done_titles(h, "long")
    n = len({x["war"] for x in h["reel"] + h["long"] if not x.get("skipped")}) + 1
    for w in WARS:
        if w not in done:
            return w, n
    w = country_war(h, done)
    if w:
        return w, n
    raise RuntimeError("agli jang nahi mili")


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
    if yr and yr < FILM_YEAR:
        era = ("this war is BEFORE film existed, so the visuals are REAL PHOTOGRAPHS and paintings of that time "
               "(battlefield photos, commanders' portraits, soldiers in camp, ships, forts). Talk about things such "
               "photos can show: the commanders, the armies, the battlefield, the cities, the ships")
    if True and not (yr and yr < FILM_YEAR):
        era = ("ONLY REAL VIDEO, NEVER pictures/paintings/maps: for 1900+ wars real archive newsreel film "
               "('<war> newsreel', '<battle> 1944 archive footage'); for every war ALSO the REAL PLACES as they look "
               "today on video - the battlefield, the fort/castle, the city, the river/mountain pass, the war memorial "
               "or war museum - always with the place and country name (e.g. 'Thermopylae pass Greece', "
               "'Waterloo battlefield Belgium', 'Edinburgh Castle Scotland')")
        shape = """a vertical REEL of 160-200 spoken words (60-75 seconds) in 7-9 scenes, in this order:
  1) a scroll-stopping hook (a shocking true number or twist from the facts), 2) WHEN and WHERE, 3) WHY it started,
  4-6) how it unfolded / the turning point, 7) WHO WON and WHO LOST, 8) how many people died (as the facts say),
  9) what it changed + "Follow Battles Untold for the story of every war in history." """
        series = (f'\nThis is part {episode} of the series "Every Country\'s Wars on Camera" - now: {REPORT.get("country", "")}, '
                  f'war number {H_COUNTRY_N[0]} of {REPORT.get("country", "")} in the series. If it is number 1, say clearly '
                  f'this was the first war of {REPORT.get("country", "")} caught on camera.')
    else:
        shape = """a LONG documentary of 800-950 spoken words (5-6 minutes) in 26-34 scenes, with these chapters
  (put the chapter name in each scene's "label"): "THE HOOK", "BEFORE THE WAR", "WHY IT STARTED", "THE SIDES",
  "HOW IT UNFOLDED", "THE TURNING POINT", "WHO WON", "THE HUMAN COST", "WHAT IT CHANGED". End with: this was
  part N of History of Every War, follow Battles Untold, like and share, comment which war we should cover next."""
        series = (f'\nThis is part {episode} of the series "Every Country\'s Wars on Camera" - now: {REPORT.get("country", "")}, '
                  f'war number {H_COUNTRY_N[0]} of {REPORT.get("country", "")} in the series. If it is number 1, say clearly '
                  f'this was the first war of {REPORT.get("country", "")} caught on camera.')
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
- If this was "the first recorded war/battle in history" / the oldest evidence of war (or similar) and the text
  says so, say it clearly. For prehistoric topics explain when humans first fought and what the evidence is,
  without describing injuries in detail.
- Strictly neutral: never praise or blame a nation, religion or ethnic group; no glorifying killing; no graphic or
  gory descriptions (Facebook monetization). Explain causes and consequences like a historian.
- ORIGINALITY: add 1-2 lines of your own historian insight (why it still matters today) - clearly as analysis.
- Era: {era}.
- For EVERY scene give "visuals": 1-3 short ENGLISH search terms, in the order the narration mentions them, naming
  the SPECIFIC thing said (the battle, the place, the commander, the ships, the trenches, the map, the fort...).
  Never generic mood shots (fire, smoke, sunset, sky, random soldiers of another era), never gore.
- "subjects": 2-5 real names from the text as exact English Wikipedia titles (the battle/war itself, key places).
{content_rules.MATCH}{content_rules.winners("war")}- If a sentence talks about something no real video can show, rewrite that sentence around a real,
  filmable thing of that war (its place, fort, river, memorial, museum) - picture and voice must always match.
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
def photo_terms(script, facts, subj):
    """Film se pehle ki jang: us ki Wikipedia articles ki ASLI tasveerein (Commons) jama karo, phir AI har jumle ke
    liye wohi tasveer chune jo bola ja raha hai (file ke naam se). Har scene ko '#img:<path>' terms milte hain."""
    pool, seen = [], set()
    for t in [facts["title"]] + subj:
        try:
            for im in war_images(t, 30):
                if im["url"] not in seen:
                    seen.add(im["url"])
                    pool.append(im)
        except Exception as e:
            log(f"  tasveer pool fail '{t}': {str(e)[:80]}")
        if len(pool) >= 60:
            break
    if len(pool) < 3:
        log("  asli tasveerein kam - sirf video talaash")
        return
    names = "\n".join(f"{k}: {im['name']}" for k, im in enumerate(pool))
    lines = "\n".join(f"{i}: {sc['text'][:300]}" for i, sc in enumerate(script["scenes"]))
    try:
        j = news.ask_json(f"""War documentary about "{facts['title']}". Real historical images (Wikimedia file names):
{names}

Narration scenes:
{lines}

For EACH scene choose 1-3 image indexes whose file name shows exactly what that scene says (the commander named,
the battle named, the place, the ships...). Use each image at most once if possible. If nothing truly fits a scene,
give []. Return JSON {{"pick": {{"0": [..], "1": [..]}}}}""")
        pick = j.get("pick") or {}
    except Exception as e:
        log(f"  tasveer chunao fail: {str(e)[:100]}")
        return
    got = 0
    for i, sc in enumerate(script["scenes"]):
        paths = []
        for k in (pick.get(str(i)) or [])[:3]:
            try:
                im = pool[int(k)]
            except Exception:
                continue
            path = os.path.join(nv.WORK, f"hist_{i}_{len(paths)}.jpg")
            url = ("https://commons.wikimedia.org/wiki/Special:FilePath/" + requests.utils.quote(im["name"].replace(" ", "_"))
                   + "?width=1600")
            try:
                if footage.download(url, path, 20000):
                    paths.append("#img:" + path)
            except Exception as e:
                log(f"  tasveer download fail {im['name'][:50]}: {str(e)[:60]}")
        if paths:
            sc["_imgs"] = paths
            got += len(paths)
            log(f"  scene {i}: asli tasveerein {[p.split('/')[-1] for p in paths]}")
    REPORT["hist_photos"] = got


def rematch_scene(sc, shown, facts):
    """Scene ki footage nahi mili: AI wohi facts rakh kar jumla us cheez ke gird likhe jo screen par dikh sakti hai."""
    opts = "\n".join(f"{k}: footage of {', '.join(v[0][:2])}" for k, v in enumerate(shown))
    try:
        j = news.ask_json(f"""A war-history reel about "{facts['title']}". This narration line has NO matching real footage:
"{sc['text']}"
Real video clips we DO have (index: what is shown):
{opts}
Pick the ONE clip that fits best and rewrite the line so it naturally talks about what that clip shows
(e.g. "Here along the Nile, ..." / "In excavations like this one, ...") while keeping the same facts, numbers and
roughly the same length. Never invent facts. Return JSON {{"clip": index, "text": "..."}}""")
        k, txt = int(j.get("clip")), str(j.get("text") or "").strip()
        if 0 <= k < len(shown) and len(txt.split()) >= 6:
            return txt, k
    except Exception as e:
        log(f"  rematch fail: {str(e)[:120]}")
    return None


class NoFilm(RuntimeError):
    pass


def build_video(script, facts, used):
    badge = (script.get("years") or "").strip() or "WAR HISTORY"
    subj = [x.strip() for x in (script.get("subjects") or []) if isinstance(x, str) and x.strip()][:5]
    if facts["title"] not in subj:
        subj.insert(0, facts["title"])
    place = (facts["infobox"].get("place") or facts["infobox"].get("location") or "").split(";")[0][:60]
    # sirf asli video (reel + long): archive film + asli jagah aaj
    fallback = [f"{facts['title']} archive footage", f"{place} battlefield", f"{place}",
                f"{facts['title']} memorial", f"{place} fort"]
    fallback = [x for x in fallback if x.strip() and x.strip() != "@"]
    nv.STORY_CLIPS.clear()
    yr = year_of(facts)
    if yr and yr < FILM_YEAR:
        photo_terms(script, facts, subj)
    # aawaz = tasveer: kisi aur scene ki clip random dobara NAHI lagegi. Jis jumle ki footage na mile,
    # wo jumla (wohi facts) us cheez ke gird dobara likha jata hai jis ki asli footage is video mein mil chuki.
    os.environ["NO_REUSE"] = "1"
    shown = []          # [(scene ki visuals, scene ka text, clip paths)] jo agent ne pass ki
    scenes = []
    real = 0            # kitne scenes ko apni asli footage mili
    for i, sc in enumerate(script["scenes"]):
        terms = list(sc.get("_imgs") or []) + [t for t in (sc.get("visuals") or []) if isinstance(t, str) and t.strip()]
        if not terms and place:
            terms = [place]
        label = str(sc.get("label") or "").strip().upper()[:40] or None
        try:
            miss0, clips0 = len(nv.REPORT.get("no_match", [])), len(nv.ALL_CLIPS)
            out = nv.build_scene(i, PAGE, sc["text"], terms, label, badge, used, fallback)
            new_clips = nv.ALL_CLIPS[clips0:]
            if len(nv.REPORT.get("no_match", [])) > miss0 and shown:
                fixed = rematch_scene(sc, shown, facts)
                if fixed:
                    txt, k = fixed
                    log(f"  scene {i}: footage nahi mili - jumla '{shown[k][0][0]}' ke gird dobara likha")
                    nv.STORY_CLIPS[:] = list(shown[k][2])
                    try:
                        out = nv.build_scene(i, PAGE, txt, ["#reuse"] * 3, label, badge, used, [])
                        sc["text"] = txt
                        new_clips = []
                    finally:
                        nv.STORY_CLIPS.clear()
            if new_clips:
                shown.append((terms or [place], sc["text"], new_clips))
                real += 1
            scenes.append(out)
        except Exception as e:
            log(f"scene {i} fail: {str(e)[:200]}")
            REPORT["errors"].append(f"scene {i}: {str(e)[:150]}")
    if len(scenes) < max(3, len(script["scenes"]) // 2):
        raise RuntimeError("bohat se scenes nahi banay")
    log(f"asli footage wale scenes: {real}/{len(script['scenes'])}")
    if real < 0.6 * len(script["scenes"]):      # aadhi video wohi 2-3 tasveerein = battles video nahi - post mat karo
        raise NoFilm(f"asli battle footage kam ({real}/{len(script['scenes'])} scenes)")
    nv.fix_cards()                     # likhe hue card ki jagah isi video ki asli clip
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


GEO_TAGS = "#USA #Canada #NewZealand #UK #Austria #UnitedStates #London #Toronto #Vienna #Auckland"


def geo(cap):
    """Har caption mein USA/Canada/NZ/UK/Austria audience ke hashtags (dollar/euro wali audience)."""
    return cap if "#NewZealand" in cap else cap.rstrip() + "\n\n" + GEO_TAGS


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
        return geo(out + (" #reels" if MODE == "reel" and "#reels" not in out.lower() else ""))
    except Exception as e:
        log(f"SEO fail ({str(e)[:100]})")
    return geo(f"⚔️ {script.get('title')}\n\n{card}\n\n{script.get('caption', '')}\n\n{src}\n\n#BattlesUntold #history #war")


BRAND_COVER = ("epic medieval battle close-up, armored knights fighting with swords in the foreground, cavalry charging, "
               "red and gold banners, burning fortress, fire sparks smoke, crimson sunset, vibrant colors, 3D render, "
               "unreal engine, ultra detailed")
BRAND_LOGO = ("3D emblem, golden spartan helmet with red crest on a steel shield with two crossed swords, glowing embers, "
              "glossy metal, vibrant colors, 3D render, unreal engine, ultra detailed, centered, dark red background, no text")


def ai_art(prompt, w, h, path, seed=77):
    """Rangeen 3D AI tasveer: pehle Pollinations (flux, free), phir Gemini image (WAR key)."""
    import urllib.parse
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) +
           f"?width={w}&height={h}&seed={seed}&model=flux&nologo=true")      # seed 77 = dekh kar chuni hui tasveer
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=240)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image") and len(r.content) > 40000:
                from PIL import Image
                import io
                im = Image.open(io.BytesIO(r.content)).convert("RGB")
                im.crop((0, 0, im.width, int(im.height * 0.93))).save(path, quality=97)   # neeche ka watermark kaat do
                log(f"brand art: pollinations ok ({w}x{h})")
                return True
            log(f"pollinations {r.status_code} (try {attempt + 1})")
        except Exception as e:
            log(f"pollinations error: {str(e)[:120]}")
        time.sleep(20 + attempt * 15)
    key = os.environ.get("WAR_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    import base64
    for model in ("gemini-2.5-flash-image", "gemini-2.0-flash-preview-image-generation"):
        try:
            j = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              params={"key": key}, timeout=180, json={
                                  "contents": [{"parts": [{"text": prompt}]}],
                                  "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}).json()
            for part in j["candidates"][0]["content"]["parts"]:
                if part.get("inlineData"):
                    open(path, "wb").write(base64.b64decode(part["inlineData"]["data"]))
                    log(f"brand art: gemini {model} ok")
                    return True
        except Exception as e:
            log(f"gemini image {model} fail: {str(e)[:120]}")
    return False


def hd(im, size):
    """Bara karo (LANCZOS) + rang tez + sharp - ultra HD look."""
    from PIL import Image, ImageEnhance, ImageFilter
    w, h = im.size
    tw, th = size
    r = tw / th
    cw, ch = (w, int(w / r)) if w / h < r else (int(h * r), h)
    im = im.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2)).resize(size, Image.LANCZOS)
    im = ImageEnhance.Color(im).enhance(1.3)
    im = ImageEnhance.Contrast(im).enhance(1.12)
    return im.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))


def text_3d(canvas, txt, font, cx, y, depth=14):
    """3D sona text: neeche gehri parteen (extrude), saya, upar sunehri gradient + chamak."""
    from PIL import Image, ImageDraw, ImageFilter
    d0 = ImageDraw.Draw(canvas)
    tw = d0.textlength(txt, font=font)
    x = cx - tw / 2
    asc, desc = font.getmetrics()
    th = asc + desc
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x + depth + 6, y + depth + 10), txt, font=font, fill=(0, 0, 0, 200))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(depth)))
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((x, y), txt, font=font, fill=(255, 140, 20, 170))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(depth * 1.6)))
    d = ImageDraw.Draw(canvas)
    for i in range(depth, 0, -1):
        k = i / depth
        d.text((x + i * 0.7, y + i), txt, font=font,
               fill=(int(90 - 50 * k), int(40 - 25 * k), int(5), 255))
    grad = Image.new("RGBA", (int(tw) + 20, th + 20))
    gd = ImageDraw.Draw(grad)
    stops = [(0.0, (255, 250, 210)), (0.45, (255, 205, 70)), (0.55, (215, 140, 20)), (1.0, (255, 225, 120))]
    for yy in range(grad.size[1]):
        t = yy / grad.size[1]
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if a <= t <= b:
                f = (t - a) / (b - a)
                gd.line([(0, yy), (grad.size[0], yy)], fill=tuple(int(ca[c] + (cb[c] - ca[c]) * f) for c in range(3)) + (255,))
                break
    mask = Image.new("L", grad.size, 0)
    ImageDraw.Draw(mask).text((10, 10), txt, font=font, fill=255)
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    out.paste(grad, (int(x) - 10, int(y) - 10), mask)
    edge = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).text((x, y), txt, font=font, fill=(0, 0, 0, 0),
                              stroke_width=max(2, depth // 5), stroke_fill=(60, 25, 0, 255))
    canvas.alpha_composite(edge)
    canvas.alpha_composite(out)


def brand():
    """Ek dafa: page ki profile (3D logo) + cover (rangeen 3D jang ka manzar), ultra HD."""
    from PIL import Image, ImageDraw, ImageFont
    P = page()
    font = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Cinzel.ttf")

    def F(n):
        try:
            return ImageFont.truetype(font, n)
        except Exception:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", n)

    def src(prompt, w, h, name):
        path = os.path.join(nv.WORK, name)
        if ai_art(prompt, w, h, path):
            return Image.open(path).convert("RGB")
        log("AI art nahi mili - asli painting se")
        for nm in ("Battle of Waterloo", "Battle of Trafalgar", "Battle of Hastings"):
            if footage.real_photo(nm, path, [], min_w=1200):
                return Image.open(path).convert("RGB")
        raise RuntimeError("brand ki tasveer nahi mili")

    # cover 2560x1440 (FB ultra HD)
    cov = hd(src(BRAND_COVER, 1280, 720, "brand_cover_src.jpg"), (2560, 1440)).convert("RGBA")
    shade = Image.new("RGBA", cov.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for yy in range(cov.size[1]):
        a = int(150 * max(0, 1 - abs(yy - 720) / 520))
        sd.line([(0, yy), (cov.size[0], yy)], fill=(0, 0, 0, a))
    cov.alpha_composite(shade)
    text_3d(cov, "BATTLES UNTOLD", F(200), 1280, 520, depth=18)
    text_3d(cov, "THE TRUE STORY OF EVERY WAR IN HISTORY", F(62), 1280, 800, depth=6)
    cov_path = os.path.join(nv.WORK, "cover.jpg")
    cov.convert("RGB").save(cov_path, quality=96, subsampling=0)

    # profile 2048x2048: 3D emblem + naam
    prof = hd(src(BRAND_LOGO, 1024, 1024, "brand_logo_src.jpg"), (2048, 2048)).convert("RGBA")
    shade = Image.new("RGBA", prof.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for yy in range(1300, 2048):
        sd.line([(0, yy), (2048, yy)], fill=(0, 0, 0, int(200 * (yy - 1300) / 748)))
    prof.alpha_composite(shade)
    text_3d(prof, "BATTLES", F(300), 1024, 1440, depth=20)
    text_3d(prof, "UNTOLD", F(230), 1024, 1760, depth=16)
    prof_path = os.path.join(nv.WORK, "profile.jpg")
    prof.convert("RGB").save(prof_path, quality=96, subsampling=0)
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
            "published": "false", "access_token": P["token"]}))["id"]
    r = requests.post(f"{GRAPH}/{P['id']}", timeout=120,
                      data={"cover": cid, "no_feed_story": "true", "access_token": P["token"]})
    log(f"cover: {r.status_code} {r.text[:200]}")


PIC_BAD = {"logo", "wordmark", "emblem", "killed", "dead", "corpse", "corpses", "bodies", "massacre", "execution",
           "executed", "gore", "atrocity", "locator", "skeleton", "skeletons", "skull", "skulls", "remains", "bones",
           "wound", "wounds", "map", "flag", "icon", "commons", "wiki", "svg", "edit", "question", "book"}


def war_images(title, n=2):
    """Jang ke Wikipedia article ki ASLI tasveerein (Commons, free license) - cave art, paintings, naqshe, khandar."""
    j = _wiki({"action": "query", "titles": title, "redirects": 1, "generator": "images", "gimlimit": 60,
               "prop": "imageinfo", "iiprop": "url|size|mime"})
    out = []
    for pg in (j.get("query") or {}).get("pages") or []:
        ii = (pg.get("imageinfo") or [{}])[0]
        name = pg.get("title", "").lower()
        toks = set(re.split(r"[^a-z]+", name))
        if ii.get("mime") not in ("image/jpeg", "image/png") or (ii.get("width") or 0) < 700 or toks & PIC_BAD:
            continue
        if "/wikipedia/commons/" not in ii.get("url", ""):
            continue
        out.append({"url": ii["url"], "name": pg.get("title", "")[5:], "w": ii["width"], "h": ii["height"]})
    out.sort(key=lambda x: -x["w"] * x["h"])
    return out[:n + 4]


def pic_card(src, path, top, line):
    """1080x1350 HD card: asli tasveer + sunehri 3D heading + ek fact."""
    from PIL import Image, ImageDraw, ImageFont
    font = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Cinzel.ttf")

    def F(n):
        try:
            return ImageFont.truetype(font, n)
        except Exception:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", n)
    W, H = 2160, 2700
    im = hd(Image.open(src).convert("RGB"), (W, H)).convert("RGBA")
    shade = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for yy in range(H):
        a = int(210 * max(0, (yy - 1500) / 1200)) + int(170 * max(0, (520 - yy) / 520))
        sd.line([(0, yy), (W, yy)], fill=(0, 0, 0, min(a, 235)))
    im.alpha_composite(shade)
    top = top.upper()
    size = 130 if len(top) <= 22 else 96 if len(top) <= 32 else 76
    text_3d(im, top, F(size), W // 2, 230, depth=10)
    d = ImageDraw.Draw(im)
    f2 = F(84)
    words, lines, cur = line.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f2) > W - 260 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    y = H - 140 - len(lines) * 112
    for ln in lines:
        d.text((W // 2, y), ln, font=f2, fill=(255, 244, 220), anchor="mt", stroke_width=5, stroke_fill=(0, 0, 0))
        y += 112
    d.text((W // 2, H - 70), "BATTLES UNTOLD", font=F(48), fill=(230, 180, 70), anchor="mm")
    im.convert("RGB").save(path, quality=95, subsampling=0)


def pics(P, h, n=2):
    """2 tasveer posts usi jang par jo aakhri reel/long mein thi (ya WAR_OVERRIDE)."""
    war = os.environ.get("WAR_OVERRIDE", "").strip()
    if not war:
        war = pick_war(json.loads(json.dumps(h)))[0]  # copy: mulk ka counter reel hi barhaye. rozana pehle pics: wohi jang jis par aaj ki reel aayegi
    facts = gather_facts(war)
    log(f"Pics jang: {facts['title']}")
    imgs = war_images(facts["title"], n)
    if not imgs:
        raise RuntimeError("is jang ki asli tasveer nahi mili")
    j = news.ask_json(f"""Facebook page "Battles Untold" (war history, neutral, only true facts).
War: {facts['title']}. Facts: {json.dumps(facts['infobox'])[:1500]} {facts['text'][:4000]}
Images available (Wikimedia file names): {json.dumps([x['name'] for x in imgs])}
Make {n} different photo posts. For each pick a DIFFERENT image (exact name from the list); prefer images that show fighting,
weapons, warriors or battle art. Heading and fact must match what the image shows (judge by its file name).
Return JSON {{"posts": [{{"image": "...", "heading": "max 4 words, e.g. THE FIRST WAR EVER", "fact": "one shocking true
fact from the facts, max 18 words", "caption": "engaging English caption 3-5 short lines with 1-2 emojis, ends with a
question to make people comment, then 5 hashtags incl #BattlesUntold #History"}}]}}""")
    done = []
    for k, p in enumerate((j.get("posts") or [])[:n]):
        im = next((x for x in imgs if x["name"] == p.get("image") and x["url"] not in done), None) or \
            next((x for x in imgs if x["url"] not in done), None)
        if not im:
            break
        raw = os.path.join(nv.WORK, f"pic_src_{k}")
        r = requests.get(im["url"], headers=UA, timeout=120)
        open(raw, "wb").write(r.content)
        out = os.path.join(nv.WORK, f"pic_{k}.jpg")
        pic_card(raw, out, p.get("heading") or "BATTLES UNTOLD", p.get("fact") or "")
        done.append(im["url"])
        cap = geo(f"{p.get('caption', '')}\n\n📸 Image: Wikimedia Commons - {im['name']}\n📚 Source: Wikipedia - {facts['title']}")
        log(f"pic {k + 1}: {p.get('heading')} | {im['name']}")
        import shutil
        shutil.copy(out, f"final_war_pic{k + 1}.jpg")
        if DRY_RUN:
            continue
        with open(out, "rb") as f:
            pid = nv.fb_json(requests.post(f"{GRAPH}/{P['id']}/photos", timeout=300, files={"source": f},
                                           data={"message": cap, "published": "true", "access_token": P["token"]}))
        pid = pid.get("post_id") or pid.get("id")
        log(f"pic posted {pid}")
        h.setdefault("pics", []).append({"war": war, "date": REPORT["time_utc"], "post_id": pid, "img": im["name"]})
        if k + 1 < n:
            time.sleep(20)
    if not DRY_RUN:
        save_hist(h)
    REPORT["posted"] = {"pics": len(done), "war": war}


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
    if MODE == "pics":
        pics(P, h)
        return
    if MODE == "delete":                    # malik ke kehne par: diye gaye post/video id page se hatao
        for vid in re.split(r"[\s,]+", os.environ.get("WAR_OVERRIDE", "").strip()):
            if vid:
                r = requests.delete(f"https://graph.facebook.com/v21.0/{vid}", params={"access_token": P["token"]},
                                    timeout=60)
                log(f"delete {vid}: {r.status_code} {r.text[:150]}")
        return
    war, episode = pick_war(h)
    if os.environ.get("WAR_OVERRIDE", "").strip():
        war = os.environ["WAR_OVERRIDE"].strip()
        episode = next((x["episode"] for x in h["reel"] + h["long"] if x["war"] == war), episode)
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
    for attempt in range(3):
        script = write_script(facts, episode)
        log(f"Title: {script.get('title')} | {len(script['scenes'])} scenes")
        if episode:
            script["title"] = f"{script.get('title') or facts['title']} | History of Every War #{episode}"
        try:
            path = build_video(script, facts, h["used_clips"])
            break
        except NoFilm as e:
            log(f"{war}: {e} - ye jang skip, agli filmi jang")
            h.setdefault("no_film", []).append(war)
            h[MODE].append({"war": war, "date": REPORT["time_utc"], "skipped": str(e)[:100]})
            h["country_n"] = max(0, h["country_n"] - 1)
            save_hist(h)
            if attempt == 2 or os.environ.get("WAR_OVERRIDE", "").strip():
                raise
            nv.ALL_CLIPS.clear()
            nv.REPORT["no_match"] = []
            war, episode = pick_war(h)
            log(f"Jang: {war} (episode {episode})")
            facts = gather_facts(war)
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
    if DRY_RUN:
        log("dry run - history mein darj nahi (jang agli dafa asli post hogi)")
        REPORT["dry"] = meta
        return
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
