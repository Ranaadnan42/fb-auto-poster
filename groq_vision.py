"""
Groq vision (clip/photo dekhne wala backup AI) - sab bots ke liye ek jagah.
Pehle masla: sirf ek model (qwen) try hota tha; 429 aate hi foran chhor deta tha aur doosra model
(llama-4-scout) Groq par band ho chuka tha -> Groq kabhi chalta hi nahi tha.
Ab: Groq se LIVE model list, har tasveer-samajhne wala model bari bari; 429 par Groq ka bataya waqt
(retry-after) chhota ho to ruk kar dobara, lamba ho to wo model aaraam par aur agla model.
"""
import base64
import json
import os
import re
import time

import requests

URL = "https://api.groq.com/openai/v1"
# tasveer samajhne wale models ke naam mein aksar ye hota hai
VISION_HINTS = ("vision", "scout", "maverick", "llama-4", "-vl", "qwen3.8", "qwen3.5", "qwen3.6", "gemma-3", "gemma-4",
                "pixtral", "llava", "kimi-k2.5", "kimi-k3")
PREFERRED = ["qwen/qwen3.8-27b", "meta-llama/llama-4-maverick-17b-128e-instruct",
             "meta-llama/llama-4-scout-17b-16e-instruct"]
_MODELS = None
_DEAD = set()
_REST = {}          # model -> kab tak aaraam
_SAID = set()


def _log(msg):
    print(f"[groq-vision] {msg}", flush=True)


def models(key):
    global _MODELS
    if _MODELS is None:
        ids = []
        try:
            r = requests.get(f"{URL}/models", headers={"Authorization": f"Bearer {key}"}, timeout=20)
            ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True)]
        except Exception as e:
            _log(f"model list fail: {str(e)[:100]}")
        vis = [i for i in ids if any(h in i.lower() for h in VISION_HINTS)]
        _MODELS = list(dict.fromkeys([m for m in PREFERRED if not ids or m in ids] + vis)) or PREFERRED
        _log(f"vision models: {', '.join(_MODELS)}")
    return _MODELS


def _wait_secs(r):
    try:
        return float(r.headers.get("retry-after") or 0)
    except Exception:
        return 0.0


def ask(images, prompt, json_mode=True):
    """images: jpg bytes ya base64 strings ki list. Wapas: model ka text, ya None (sab band/busy)."""
    key = os.environ.get("GROQ_API_KEY")
    if not key or not images:
        return None
    b64 = [i if isinstance(i, str) else base64.b64encode(i).decode() for i in images][:5]
    content = [{"type": "text", "text": prompt}] + [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}} for b in b64]
    for m in models(key):
        if m in _DEAD or _REST.get(m, 0) > time.time():
            continue
        body = {"model": m, "temperature": 0, "max_tokens": 300, "messages": [{"role": "user", "content": content}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for attempt in range(3):
            try:
                r = requests.post(f"{URL}/chat/completions", timeout=60, json=body,
                                  headers={"Authorization": f"Bearer {key}"})
            except Exception as e:
                _log(f"{m}: {str(e)[:80]}")
                break
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            txt = r.text[:200]
            if r.status_code == 429:
                w = _wait_secs(r)
                if m not in _SAID:
                    _SAID.add(m)
                    _log(f"{m} limit: {txt}")
                if 0 < w <= 25 and attempt < 2:
                    time.sleep(w + 1)          # minute wali limit - thora ruk kar dobara
                    continue
                _REST[m] = time.time() + max(w, 120)   # lambi limit - is model ko aaraam, agla model
                break
            if r.status_code == 400 and json_mode and "json" in txt.lower():
                body.pop("response_format", None)      # kuch models json mode nahi lete
                continue
            if r.status_code in (400, 401, 403, 404):
                _DEAD.add(m)
                _log(f"{m} band: {r.status_code} {txt[:120]}")
                break
            time.sleep(3)
    return None


def ask_json(images, prompt):
    t = ask(images, prompt)
    if not t:
        return None
    try:
        return json.loads(re.search(r"\{.*\}", t, re.S).group(0))
    except Exception:
        return None
