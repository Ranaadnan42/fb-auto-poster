"""Agent ka zubaan wala faisla: jis zubaan ke views zyada, kuch slots us mein badal do (max 40%).
python3 tools/brain_lang.py reel_ur  ->  reel_ur ya reel_en print karta hai. long/match/manual nahi badalte."""
import json
import random
import sys

m = sys.argv[1] if len(sys.argv) > 1 else ""
kind, _, lang = m.partition("_")
try:
    flip = json.load(open("news_brain.json", encoding="utf-8")).get("lang_flip") or {}
except Exception:
    flip = {}
if kind in ("pic", "reel", "breaking") and lang in ("ur", "en"):
    p = float(flip.get("ur_to_en" if lang == "ur" else "en_to_ur", 0) or 0)
    if random.random() < min(p, 0.4):
        lang = "en" if lang == "ur" else "ur"
print(f"{kind}_{lang}")
