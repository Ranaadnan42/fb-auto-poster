"""
Web Builder ke har post ka apna rang-theme (pic / reel / long video, har zubaan).
Koi fixed list nahi: har dafa naya rang (hue) aur shade random banta hai.
AGENT wala hissa:
  - pichle posts ke rang (history) dekh kar unse door ka naya rang chunta hai (kabhi repeat nahi lagta)
  - wb_brain.py jo seekhta hai (kaun se rang wale posts zyada dekhe gaye -> color_mult)
    us taraf thora jhukao rakhta hai, magar har dafa rang phir bhi naya hota hai.
"""
import colorsys
import json
import os
import random
import time

_rnd = random.Random(time.time_ns() ^ os.getpid())
PLAN_FILE = "webbuilder_brain.json"
HIST_FILES = ("webbuilder_history.json", "webbuilder_video_history.json")
MIN_GAP = 35          # pichle posts ke rang se kam az kam itne darje door


def family(hue_deg):
    """Rang ka khandan (12 hisse, har 30 darje) - brain isi se seekhta hai."""
    return str(int(hue_deg % 360) // 30)


def recent_hues(n=8):
    rows = []
    for f in HIST_FILES:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        d = d.get("posts", []) if isinstance(d, dict) else d
        rows += [(r.get("date", ""), r["hue"]) for r in d if isinstance(r, dict) and r.get("hue") is not None]
    return [h for _, h in sorted(rows)[-n:]]


def _plan_mult():
    try:
        return json.load(open(PLAN_FILE, encoding="utf-8")).get("color_mult") or {}
    except Exception:
        return {}


def _gap(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _choose_hue(avoid=()):
    recent = recent_hues() + list(avoid)
    mult = _plan_mult()
    cands = [_rnd.uniform(0, 360) for _ in range(40)]
    far = [h for h in cands if all(_gap(h, r) >= MIN_GAP for r in recent)] or \
        sorted(cands, key=lambda h: -min([_gap(h, r) for r in recent] or [360]))[:5]
    w = [float(mult.get(family(h), 1.0)) for h in far]
    return _rnd.choices(far, weights=w)[0]


def _hsv(h, s, v):
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1.0, s, v))


def _hex(c):
    return "%02X%02X%02X" % c


def _ass(c):          # RGB -> ASS &H00BBGGRR
    return "&H00%02X%02X%02X" % (c[2], c[1], c[0])


def pick(kind="pic", lang="en", avoid=()):
    deg = _choose_hue(avoid)
    h = deg / 360
    accent = _hsv(h, _rnd.uniform(0.55, 0.85), _rnd.uniform(0.88, 1.0))
    h2 = h + _rnd.choice([0.33, 0.5, 0.58, -0.25])       # doosra (badge) rang, accent se alag
    accent2 = _hsv(h2, _rnd.uniform(0.55, 0.8), 1.0)
    dark = _hsv(h, _rnd.uniform(0.6, 0.85), _rnd.uniform(0.08, 0.15))
    g1 = _hsv(h + _rnd.uniform(-0.08, 0.08), _rnd.uniform(0.6, 0.9), _rnd.uniform(0.35, 0.55))
    return {"name": "hue%03d" % int(deg), "hue": round(deg, 1), "accent": accent, "accent2": accent2, "dark": dark,
            "accent_hex": _hex(accent), "accent2_hex": _hex(accent2), "dark_hex": _hex(dark),
            "accent_ass": _ass(accent), "accent2_ass": _ass(accent2), "dark_ass": _ass(dark),
            "grad": ("0x" + _hex(dark), "0x" + _hex(g1)), "tint": "0x" + _hex(dark)}
