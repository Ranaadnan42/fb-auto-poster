"""
AI employee ki content hidayat (content_rules.json) - har bot apne idea/script prompt mein yeh parhta hai.
AI employee (tools/content_review.py) roz pichhli videos dekh kar likhta hai: kya bar bar repeat ho raha hai
(is se bacho) aur naye andaaz/topics (yeh try karo). File na ho to kuch nahi badalta.
"""
import json
import os

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_rules.json")


def text(bot):
    try:
        r = (json.load(open(FILE, encoding="utf-8")).get(bot) or {})
    except Exception:
        return ""
    avoid, fresh = r.get("avoid") or [], r.get("try") or []
    if not avoid and not fresh:
        return ""
    out = "\nCONTENT EDITOR NOTES (from the page's reviewer - follow them):"
    if avoid:
        out += "\n- Recent videos repeated these too much - do NOT use them again now: " + "; ".join(avoid[:12])
    if fresh:
        out += "\n- Prefer fresh directions like: " + "; ".join(fresh[:8])
    return out + "\n"
