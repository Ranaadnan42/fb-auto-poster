"""Urdu TTS test: har candidate ki awaaz banao, Whisper se wapas likhwao (kaan ki jagah)."""
import asyncio, json, edge_tts
from faster_whisper import WhisperModel
C = {
 "A_plain": "حضرت محمد صلی اللہ علیہ وسلم نے فرمایا",
 "B_harakat": "حضرت مُحَمَّد صَلَّی اللّٰہُ عَلَیْہِ وَسَلَّم نے فرمایا",
 "C_shadd": "حضرت محمد صلّی اللہ علیہ وسلّم نے فرمایا",
 "D_hyphen": "حضرت محمد صل-لل-لاہو علیہ-وسلم نے فرمایا",
 "E_seen": "حضرت محمد سَلّلّاہُو عَلَیہِ وَسَلّم نے فرمایا",
 "F_sallallahu": "حضرت مُحَمَّد صَلَّ اللّٰہُ عَلَیْہِ وَ آلِہٖ وَسَلَّم نے فرمایا",
 "G_ligature": "حضرت محمد ﷺ نے فرمایا",
 "H_nabi": "نبی کریم صَلَّی اللّٰہُ عَلَیْہِ وَسَلَّم نے ارشاد فرمایا",
 "I_rasool": "رَسُولُ اللّٰہ صَلَّی اللّٰہُ عَلَیْہِ وَسَلَّم کی سنت",
 "J_words": "بِسْمِ اللّٰہ، اَلْحَمْدُ لِلّٰہ، اِنْ شَاءَ اللّٰہ، سُبْحَانَ اللّٰہ، صبر، تقویٰ، جنت",
 "K_hyphwords": "بس-م-اللہ، ال-حم-دو-لل-لاہ، ان-شا-اللہ، سب-حان-اللہ",
}
async def mk(k, t):
    await edge_tts.Communicate(t, "ur-PK-AsadNeural", rate="-4%").save(f"tts_test/{k}.mp3")
import os; os.makedirs("tts_test", exist_ok=True)
for k, t in C.items():
    asyncio.run(mk(k, t))
m = WhisperModel("large-v3", device="cpu", compute_type="int8")
out = {}
for k, t in C.items():
    segs, _ = m.transcribe(f"tts_test/{k}.mp3", language="ur", beam_size=5)
    out[k] = {"in": t, "heard": " ".join(s.text for s in segs).strip()}
    print(k, "|", out[k]["heard"], flush=True)
json.dump(out, open("tts_test/result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
