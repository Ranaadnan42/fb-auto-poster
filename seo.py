"""
SEO captions for Facebook posts (dono pages).
Format:
  1) Hook line (emoji ke saath) - pehli line jo feed mein nazar aati hai
  2) 1-2 lines jin mein log jo search karte hain woh keywords hon (Urdu + Roman Urdu + English)
  3) Comment/share/follow ka sawal (engagement)
  4) 6-10 hashtags: 2-3 bare (#reels #viral), 3-4 niche, 1 page ka apna
"""
import json
import re

PAGES = {
    "funny": {
        "name": "Hansi Ka Adda",
        "brand_tags": ["#HansiKaAdda"],
        "base_tags": ["#funny", "#comedy", "#reels", "#pakistanicomedy", "#urducomedy",
                      "#funnyvideo", "#viral"],
        "audience": "Pakistani / Urdu-speaking people who love desi comedy, memes and funny reels",
        "cta": "روز نئی مزاحیہ ویڈیوز کے لیے پیج فالو کریں 👈",
    },
    "islamic": {
        "name": "Islamic Motivational Videos",
        "brand_tags": ["#IslamicMotivationalVideos"],
        "base_tags": ["#islam", "#islamicreminder", "#islamicvideo", "#reels", "#muslim",
                      "#deen", "#viral"],
        "audience": "Muslims (Pakistan, India, Gulf, worldwide) looking for Islamic reminders and motivation",
        "cta": "روزانہ اسلامی یاد دہانی کے لیے پیج فالو کریں اور شیئر کریں 👈",
        "cta_en": "Follow the page for daily Islamic reminders 👈",
    },
    "frames": {
        "name": "Frames Of Life",
        "brand_tags": ["#FramesOfLife"],
        "base_tags": ["#abroad", "#visa", "#jobsabroad", "#costofliving", "#pakistanabroad",
                      "#documentary", "#viral"],
        "audience": ("Pakistanis and Urdu speakers who want to live, work, study or travel abroad "
                     "(Gulf, Europe, UK, Canada, etc.) and want to know cost of living, visas, jobs and life there"),
        "cta": "باہر کی زندگی، ویزا اور نوکری کی روزانہ معلومات کے لیے پیج فالو کریں 👈",
    },
    "news": {
        "name": "News Act",
        "brand_tags": ["#NewsAct"],
        "base_tags": ["#news", "#worldnews", "#breakingnews", "#latestnews", "#urdunews", "#viral"],
        "audience": ("Urdu and English speakers in Pakistan, the Gulf, India, UK and USA who follow world news, "
                     "Pakistan news, America news and Middle East news"),
        "cta": "دنیا بھر کی تازہ خبروں کے لیے News Act کو فالو کریں 👈",
        "cta_en": "Follow News Act for world news every day 👈",
        "rules": ("the hook/body may ONLY restate facts from 'What the video says' - never add or exaggerate "
                  "(no 'massive', 'shocking', 'watch highlights' unless stated); strictly neutral, no political opinion; "
                  "no meta hashtags like #UrduEnglish; max 2 emojis per line."),
    },
    "sports": {
        "name": "Sports Hubs",
        "brand_tags": ["#SportsHubs"],
        "base_tags": ["#sports", "#sportsnews", "#sportsupdate", "#cricket", "#football", "#viral"],
        "audience": ("sports fans worldwide (Pakistan, India, Gulf, UK, USA) - cricket, football, tennis, F1, NBA, "
                     "hockey, UFC and every other sport"),
        "cta": "دنیا بھر کے کھیلوں کی ہر خبر کے لیے Sports Hubs کو فالو کریں 👈",
        "cta_en": "Follow Sports Hubs for every sport from around the world 👈",
        "rules": ("the hook/body may ONLY restate facts from 'What the video says' - never invent or exaggerate scores, "
                  "results or records; no 'watch highlights' unless stated; no meta hashtags like #UrduEnglish; "
                  "max 2 emojis per line."),
    },
}


def _clean_tag(t):
    t = re.sub(r"[^\w#]", "", (t or "").strip().replace(" ", ""))
    if not t:
        return ""
    return t if t.startswith("#") else "#" + t


def build(ask_json, page, title, script_text, lang="ur", is_reel=True, search_terms=None):
    """Gemini se SEO caption banwata hai. Fail ho to simple caption.
    search_terms: YouTube par asal search hone wale phrases (ho to keywords inhi se)."""
    P = PAGES[page]
    lang_name = "Urdu (Urdu script)" if lang == "ur" else "English"
    real = ""
    if search_terms:
        real = ("\nReal phrases people search on YouTube for this topic (use the ones that match "
                f"this video in the body words and hashtags): {json.dumps(search_terms, ensure_ascii=False)}")
    try:
        d = ask_json(f"""You are a Facebook growth/SEO expert. Write the post caption for a
{'Reel' if is_reel else 'video'} on the page "{P['name']}". Audience: {P['audience']}.
Video title: {title}
What the video says: {script_text[:1500]}{real}

Return JSON:
{{"hook": "one short scroll-stopping first line in {lang_name} with 1-2 fitting emojis",
 "body": "1-2 short lines in {lang_name} that naturally include the words people SEARCH for this topic",
 "keywords": "one line of 4-6 search keywords in Roman Urdu and English separated by ' | ' (e.g. funny video | pakistani comedy | ammi beta comedy)",
 "question": "one short question in {lang_name} that makes people comment or tag a friend",
 "hashtags": ["6 specific, popular, searchable topic hashtags in English or Roman Urdu, no spaces"]}}
Rules: {P.get("rules") or "no fake claims, no clickbait lies, no politics, no religious mockery, max 2 emojis per line."}""")
        hook = (d.get("hook") or title).strip()
        body = (d.get("body") or "").strip()
        kw = (d.get("keywords") or "").strip()
        q = (d.get("question") or "").strip()
        gen_tags = [_clean_tag(t) for t in d.get("hashtags", [])]
    except Exception as e:
        print(f"[seo] fallback: {e}", flush=True)
        hook, body, kw, q, gen_tags = title, "", "", "", []
    tags, seen = [], set()
    for t in P["brand_tags"] + gen_tags + P["base_tags"]:
        t = _clean_tag(t)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            tags.append(t)
    tags = tags[:10]
    parts = [hook]
    if body:
        parts.append(body)
    if q:
        parts.append(q)
    parts.append(P.get("cta_en") if (lang == "en" and P.get("cta_en")) else P["cta"])
    parts.append(" ".join(tags))
    return "\n\n".join(parts).strip()
