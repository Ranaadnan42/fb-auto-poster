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


def text(bot):
    try:
        import trend_scout
        tr = trend_scout.text(bot)
    except Exception:
        tr = ""
    return MATCH + _text(bot) + _brain_tips(bot) + tr


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
