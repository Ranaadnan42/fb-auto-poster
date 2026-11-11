"""
Footage AGENT (News Act, Sports Hubs, match recap) - har clip lagne se pehle AI khud dekhta hai.

Pehle: koi check nahi tha - Pixabay ki clip bina kisi lafz ke match ke bhi lag jati thi, aur na mile to
"news studio / city skyline" jaisi aam clip. Ab:
  1) check(): clip ke 2 frames + us waqt ki narration -> Gemini (kai models, page ki apni key + spare key),
     busy/quota ho to Groq vision. Jawab: True (wohi cheez) / False (be-taalluq) / None (check na ho saka).
  2) alt_terms(): kuch na mile to agent khud soche ke yeh cheez dunya ki stock/archive sites par
     aur kin alfaaz se milegi (doosre naam, jagah, mulk, khel ka manzar).
Waqt ki had: run atke nahi - had ke baad sirf Groq, warna None (phir sirf pakka lafz-match chalta hai).
"""
import base64
import json
import os
import re
import time

import requests

T0 = time.time()
BUDGET_S = int(os.environ.get("AGENT_VISION_MIN", "40")) * 60
MODELS = ["gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3-flash-preview",
          "gemini-3.5-flash", "gemini-flash-latest", "gemma-4-26b-a4b-it"]
_DEAD = set()
_REST = {}
STATS = {"agent_checks": 0, "agent_rejects": 0, "agent_skips": 0}


def _keys():
    page = (os.environ.get("AGENT_PAGE") or "").upper()
    ks = [os.environ.get(f"{page}_GEMINI_API_KEY") if page else None, os.environ.get("GEMINI_API_KEY")]
    return [k for k in dict.fromkeys(ks) if k]


def _parse(txt):
    m = re.search(r"\{[\s\S]*?\}", txt or "")
    if m:
        try:
            return bool(json.loads(m.group(0)).get("match"))
        except Exception:
            pass
    low = (txt or "").lower()
    if "false" in low:
        return False
    if "true" in low:
        return True
    return None


def _prompt(n, want, said, kind):
    sport = ("For sports: it must be THE SAME SPORT (cricket is not baseball, football is not rugby/American "
             "football), and if a team/country is named, not obviously another country's setting. "
             if kind == "sports" else "")
    return (f"You are the footage-checking agent of a {'sports' if kind == 'sports' else 'world news'} channel. "
            f"These {n} frame(s) are from ONE stock/archive clip found for '{want}'. "
            f"The anchor is saying right now: \"{(said or want)[:350]}\". "
            f"Does this clip really show {want} (real camera footage or real photo, not cartoon/CGI/AI art) so it "
            "matches what is being said? Say false if ANY frame shows something unrelated: a different country, "
            "city or landmark than the one being talked about, a different sport, a generic office/laptop/people "
            "shot, a random nature scene, or text/logos of another channel. " + sport +
            "Answer JSON {\"match\": true/false, \"why\": \"max 8 words\"}")


def is_greenscreen(jpg):
    """Hara/neela parda (chroma key) wali clip - news mein kabhi nahi."""
    import subprocess
    try:
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", jpg, "-vf", "scale=32:32", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=30).stdout
        px = [raw[i:i + 3] for i in range(0, len(raw) - 2, 3)]
        key = sum(1 for r, g, b in px if (g > 150 and g > r * 1.6 and g > b * 1.6) or
                  (b > 150 and b > r * 2 and b > g * 1.6 and g > 60))
        return bool(px) and key / len(px) > 0.30
    except Exception:
        return False


def check(jpgs, want, said="", kind="news"):
    if any(is_greenscreen(j) for j in (jpgs if isinstance(jpgs, (list, tuple)) else [jpgs])):
        return False
    datas = []
    for j in jpgs if isinstance(jpgs, (list, tuple)) else [jpgs]:
        try:
            datas.append(open(j, "rb").read())
        except Exception:
            pass
    if not datas:
        return None
    prompt = _prompt(len(datas), want, said, kind)
    if time.time() - T0 < BUDGET_S:
        b64 = [base64.b64encode(d).decode() for d in datas]
        for ki, key in enumerate(_keys()):
            for m in MODELS:
                if (ki, m) in _DEAD or _REST.get(m, 0) > time.time():
                    continue
                try:
                    r = requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}",
                        timeout=35, json={"contents": [{"parts": [{"text": prompt}] + [
                            {"inline_data": {"mime_type": "image/jpeg", "data": b}} for b in b64]}],
                            "generationConfig": {"temperature": 0}})
                    if r.status_code in (400, 401, 403, 404, 429):
                        _DEAD.add((ki, m))
                        continue
                    if r.status_code >= 500:
                        _REST[m] = time.time() + 120
                        continue
                    v = _parse(r.json()["candidates"][0]["content"]["parts"][0]["text"])
                    if v is not None:
                        return _count(v)
                except Exception:
                    _REST[m] = time.time() + 120
    try:
        import groq_vision
        t = groq_vision.ask(datas, prompt, json_mode=False)
        v = _parse(t) if t else None
        if v is not None:
            return _count(v)
    except Exception:
        pass
    STATS["agent_skips"] += 1
    return None


def _count(v):
    STATS["agent_checks"] += 1
    if not v:
        STATS["agent_rejects"] += 1
    return v


def alt_terms(want, said, ask_json, kind="news"):
    """Agent soche: yeh cheez dunya bhar ki stock/archive sites (Pixabay, Wikimedia Commons, NASA,
    Internet Archive, Mixkit) par aur kin alfaaz se milegi."""
    try:
        d = ask_json(f"""A {'sports' if kind == 'sports' else 'news'} video needs real footage of: "{want}".
The anchor says: "{(said or '')[:300]}"
Searching free stock/archive video sites with the obvious words found nothing that matches.
Give 6 OTHER short English search phrases (1-4 words) that would find footage truly showing this same thing:
its other names, the exact city/country/landmark/building, the sport being played in that place, typical
visible scenes. Every phrase must still show THIS thing (and its country if relevant), never something
generic, never a person's name, never violence/weapons. Return JSON {{"queries": ["..."]}}""")
        return [q for q in (d.get("queries") or []) if isinstance(q, str) and q.strip()][:6]
    except Exception:
        return []
