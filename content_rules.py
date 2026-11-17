"""
AI employee ki content hidayat (content_rules.json) - har bot apne idea/script prompt mein yeh parhta hai.
AI employee (tools/content_review.py) roz pichhli videos dekh kar likhta hai: kya bar bar repeat ho raha hai
(is se bacho) aur naye andaaz/topics (yeh try karo). File na ho to kuch nahi badalta.
"""
import json
import os

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_rules.json")


def _brain_tips(bot):
    """Agent (funny_brain.py) ne views se jo seekha."""
    if bot != "funny":
        return ""
    try:
        t = json.load(open("funny_brain.json", encoding="utf-8")).get("tips") or []
    except Exception:
        return ""
    if not t:
        return ""
    return "\nLESSONS FROM WHAT MADE OUR VIEWERS LAUGH AND SHARE MOST (follow them):\n" + \
        "\n".join(f"- {x}" for x in t[:6]) + "\n"


# Malik ki pakki hidayat - HAR video agent ke script prompt mein jati hai
MATCH = """
OWNER'S FIRM RULE - THE VIDEO MUST SHOW EXACTLY WHAT IS BEING SAID:
- Every scene's footage/search terms must name the SAME exact thing the narration says at that moment
  (a dish -> that exact dish of that country; a city -> that city; an animal -> that animal; a mosque -> that mosque).
- Write narration only about things that can be shown with real stock footage. If something can't be filmed
  (an abstract idea, a visa rule, a feeling), say it over a concrete visible thing that fits it and name that thing.
- Never use a generic or unrelated clip just to fill time. If no matching footage exists, change the scene's
  words to a visible thing that does have footage - viewers leave the moment picture and voice don't match.
"""


# bot -> page_manager.json ka page (Page Manager 28 din ke asli engagement se top posts nikalta hai)
_PAGE = {"funny": "funny", "islamic": "islamic", "frames": "frames", "war": "war", "birds": "birds",
         "pets": "pets", "wild": "wild", "scenic": "scenic", "news": "news", "newsur": "newsur",
         "sports": "sports", "faizi": "faizi"}


def winners(bot):
    """Is page ki 28 din ki sab se zyada chali posts - agent inhi jaisi aur banaye (market tools sirf
    dikhate hain, hamara agent khud seekhta hai)."""
    page = _PAGE.get(bot)
    if not page:
        return ""
    d = os.path.dirname(FILE)
    try:
        miss = (json.load(open(os.path.join(d, "match_audit.json"), encoding="utf-8")).get(page) or {}).get("lessons") or []
    except Exception:
        miss = []
    audit = ""
    if miss:
        audit = ("\nMANAGER'S CHECK OF OUR LAST VIDEOS - picture did NOT match the voice here (never repeat this; "
                 "name an exact, filmable subject and use footage of exactly that):\n" +
                 "\n".join(f"- {m}" for m in miss[-5:]) + "\n")
    try:
        p = json.load(open(os.path.join(d, "page_manager.json"), encoding="utf-8")).get(page) or {}
    except Exception:
        return audit
    top = [t for t in (p.get("top_posts") or []) if t.get("text") and t.get("eng", 0) > 0]
    if not top:
        return audit
    out = ("\nOUR AUDIENCE'S FAVOURITES (real engagement, last 28 days) - make today's piece in the same spirit "
           "(similar hook, emotion and kind of subject), but NEVER repeat the same subject:")
    for t in top[:3]:
        out += f"\n- {t['text']} ({t['eng']} reactions+comments+shares)"
    if p.get("eng_avg"):
        out += f"\n- Average post gets {p['eng_avg']}; aim higher with a stronger first line."
    return audit + out + "\n"


def text(bot):
    try:
        import trend_scout
        tr = trend_scout.text(bot)
    except Exception:
        tr = ""
    return MATCH + _text(bot) + _brain_tips(bot) + winners(bot) + tr


def _text(bot):
    try:
        r = (json.load(open(FILE, encoding="utf-8")).get(bot) or {})
    except Exception:
        return ""
    avoid, fresh = r.get("avoid") or [], r.get("try") or []
    if not avoid and not fresh:
        return ""
    out = "\nCONTENT EDITOR NOTES (from the page's reviewer - follow them):"
    if avoid:
        out += ("\n- These SPECIFIC subjects were used too often recently - pick a different specific one "
                "(today's theme/series itself is fine): " + "; ".join(avoid[:12]))
    if fresh:
        out += ("\n- Fresh ideas you MAY use if they fit today's theme and all the rules: " + "; ".join(fresh[:8]))
    return out + "\n"
