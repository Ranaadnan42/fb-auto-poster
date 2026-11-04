"""Hamara asli kaam dikhane ke liye: Web Builder ki banayi hui demo websites aur apps ke screenshots.

Har video / pic mein mock screen ki jagah hamari banayi hui ek asli demo website ya app (client-hunt)
ki tasveer lagti hai - har dafa alag business, repeat nahi (USED list history se aati hai).
"""
import json
import os
import random
import subprocess

import requests

LIST_URL = "https://fobzocsluzwcqretshnm.supabase.co/functions/v1/showcase?n=60"
SITE = "https://client-hunt-six.vercel.app"
USED_FILE = "showcase_history.json"
CAT = {"restaurant": ["restaurant", "cafe"], "cafe": ["cafe", "restaurant"], "grocery store": ["grocery"],
       "supermarket": ["grocery"], "beauty salon": ["salon"], "car workshop": ["auto"], "bakery": ["bakery", "cafe"],
       "clothing shop": ["fashion"], "pharmacy": ["pharmacy", "clinic"], "electronics shop": ["electronics"],
       "mobile phone shop": ["electronics"], "furniture store": ["furniture"], "hardware store": ["construction"]}
_LIST = None
USED = []
NEW = []


def _load_used():
    global USED
    try:
        USED = json.load(open(USED_FILE, encoding="utf-8"))
    except Exception:
        USED = []


def save_used():
    if not NEW:
        return
    try:
        with open(USED_FILE, "w", encoding="utf-8") as f:
            json.dump((USED + NEW)[-200:], f)
    except Exception:
        pass


def pick(spot):
    """Spot (e.g. 'restaurant') se milti hui demo jo pehle kabhi na dikhayi ho."""
    global _LIST
    if _LIST is None:
        try:
            _LIST = requests.get(LIST_URL, timeout=30).json()
        except Exception as e:
            print(f"showcase list fail: {str(e)[:100]}", flush=True)
            _LIST = []
        _load_used()
    seen = set(USED + NEW)
    fresh = [d for d in _LIST if d["id"] not in seen] or [d for d in _LIST if d["id"] not in NEW]
    want = CAT.get(spot, [])
    match = [d for d in fresh if d.get("category") in want]
    pool = match or fresh
    if not pool:
        return None
    d = random.choice(pool)
    NEW.append(d["id"])
    return d["id"]


def shot(demo_id, kind, path, mobile=True, tab=None):
    """kind 'website' -> /d/<id> (poora lamba page), 'app' -> /app/<id>. PNG path wapas, ya None."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    url = f"{SITE}/{'app' if kind == 'app' else 'd'}/{demo_id}"
    vp = dict(width=412, height=732) if mobile else dict(width=1280, height=720)
    try:
        with sync_playwright() as p:
            try:
                b = p.chromium.launch(channel="chrome")
            except Exception:
                b = p.chromium.launch()
            pg = b.new_page(viewport=vp, device_scale_factor=(1080 / 412 if mobile else 1.5),
                            is_mobile=mobile, has_touch=mobile)
            pg.goto(url, wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(2500)
            # demo ribbon / toast chhupa do - sirf design dikhe
            pg.add_style_tag(content=".ribbon,.demo-ribbon,#ribbon,.toast,.tt{display:none!important}")
            if tab:
                try:
                    pg.click(f".tabs button[data-t='{tab}']", timeout=3000)
                    pg.wait_for_timeout(1200)
                except Exception:
                    pass
            if kind == "website":   # lazy pics load hon
                for y in range(0, 6000, 600):
                    pg.mouse.wheel(0, 600)
                    pg.wait_for_timeout(150)
                pg.evaluate("window.scrollTo(0,0)")
                pg.wait_for_timeout(800)
            pg.screenshot(path=path, full_page=(kind == "website"))
            b.close()
        return path if os.path.getsize(path) > 30000 else None
    except Exception as e:
        print(f"showcase shot fail {demo_id}: {str(e)[:150]}", flush=True)
        return None


def scroll_clip(img, out, secs, W, H):
    """Lambi screenshot ko upar se neeche scroll karti video (jaise phone par website chal rahi ho)."""
    fr = max(30, int(secs * 30))
    vf = (f"scale={W}:-2,pad=iw:max(ih\\,{H}):0:0:white,"
          f"crop={W}:{H}:0:'min(ih-{H}\\,(ih-{H})*n/{fr})',fps=30,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", img, "-vf", vf,
                    "-frames:v", str(fr), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", out], check=True)
    return out
