"""Kaggle speed test: 6 clips normal vs FAST (CausVid). Clips previews branch par."""
import kaggle_video, json
P = ["Epic wide cinematic shot, a giant dragon flying over a burning medieval castle at night, embers, dramatic camera motion",
     "Epic wide cinematic shot, a lone warrior seen from behind walking through a snowy mountain pass, wind and snow",
     "Epic wide cinematic shot, an ancient glowing forest with floating lights, a small figure with a lantern in the distance",
     "Epic wide cinematic shot, a huge stone titan rising from a frozen lake, ice cracking, mist",
     "Epic wide cinematic shot, an army of knights on horses charging across a field at sunset, dust",
     "Epic wide cinematic shot, a magical portal opening in a desert canyon, swirling blue light, sand blowing"]
jobs = [{"id": i, "prompt": p, "seed": 100 + i} for i, p in enumerate(P)]
got = kaggle_video.generate(jobs, 640, 640, "work_test", print, max_minutes=120, steps=8, fast=True)
print("GOT", json.dumps({k: v for k, v in got.items()}))
