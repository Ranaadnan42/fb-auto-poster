"""Atlas awaaz check: user wali video sun kar likho + Ryan TTS ki kai dafa test (kat to nahi rahi?)."""
import asyncio, json, os, subprocess, edge_tts
from faster_whisper import WhisperModel
os.makedirs("tts_test", exist_ok=True)
T = ["Lisbon sits on seven hills above the Tagus River, where yellow trams climb narrow cobbled streets.",
     "Local eateries serve iconic pastel de nata, warm custard tarts dusted with cinnamon.",
     "Across the nation of Portugal, life moves at a gentle pace, with long lunches and late dinners."]
async def mk(t, p, rate):
    await edge_tts.Communicate(t, "en-GB-RyanNeural", rate=rate).save(p)
def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout.strip() or 0)
m = WhisperModel("small", device="cpu", compute_type="int8")
out = {"user": [], "tts": []}
segs, _ = m.transcribe("tts_test/user_atlas.mp3", language="en", word_timestamps=True)
for s in segs:
    out["user"].append(f"{s.start:.1f}-{s.end:.1f} {s.text}")
    print("USER", out["user"][-1], flush=True)
for i, t in enumerate(T):
    for r in range(3):
        p = f"tts_test/r{i}_{r}.mp3"
        try:
            asyncio.run(mk(t, p, "-6%"))
            h = " ".join(s.text for s in m.transcribe(p, language="en")[0]).strip()
            out["tts"].append({"in": t, "dur": dur(p), "heard": h})
        except Exception as e:
            out["tts"].append({"in": t, "err": str(e)[:200]})
        print("TTS", out["tts"][-1], flush=True)
json.dump(out, open("tts_test/atlas_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
