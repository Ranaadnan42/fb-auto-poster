"""
Web Builder ke har post ka apna rang-theme (pic / reel / long video, har zubaan).
Koi fixed list nahi: har dafa naya rang (hue) aur shade random banta hai,
is liye har pic / reel / video ka rang alag hota hai.
"""
import colorsys
import os
import random
import time

_rnd = random.Random(time.time_ns() ^ os.getpid())


def _hsv(h, s, v):
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1.0, s, v))


def _hex(c):
    return "%02X%02X%02X" % c


def _ass(c):          # RGB -> ASS &H00BBGGRR
    return "&H00%02X%02X%02X" % (c[2], c[1], c[0])


def pick(kind="pic", lang="en"):
    h = _rnd.random()                                   # har dafa naya rang
    accent = _hsv(h, _rnd.uniform(0.55, 0.85), _rnd.uniform(0.88, 1.0))
    h2 = h + _rnd.choice([0.33, 0.5, 0.58, -0.25])       # doosra (badge) rang, accent se alag
    accent2 = _hsv(h2, _rnd.uniform(0.55, 0.8), 1.0)
    dark = _hsv(h, _rnd.uniform(0.6, 0.85), _rnd.uniform(0.08, 0.15))
    g1 = _hsv(h + _rnd.uniform(-0.08, 0.08), _rnd.uniform(0.6, 0.9), _rnd.uniform(0.35, 0.55))
    return {"name": "hue%03d" % int(h * 360), "accent": accent, "accent2": accent2, "dark": dark,
            "accent_hex": _hex(accent), "accent2_hex": _hex(accent2), "dark_hex": _hex(dark),
            "accent_ass": _ass(accent), "accent2_ass": _ass(accent2), "dark_ass": _ass(dark),
            "grad": ("0x" + _hex(dark), "0x" + _hex(g1)), "tint": "0x" + _hex(dark)}
