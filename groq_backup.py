"""
Groq backup brain: jab Gemini ki daily limit (429) khatam ho jaye to yeh JSON jawab deta hai.
Secret: GROQ_API_KEY (na ho to kuch nahi karta - purana error hi aata hai).
"""
import json
import re
import os
import time

import requests

MODELS = ["llama-3.1-405b", "qwen-2.5-32b", "llama-3.1-8b-instant"]


def enabled():
    return bool(os.environ.get("GROQ_API_KEY"))


# Pasand ki tarteeb. Asal list Groq se live mangwai jati hai, is liye koi model band ho ya
# ghalat naam likha ho to bhi kaam nahi rukta.
PREFERRED = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3-32b", "openai/gpt-oss-20b",
             "llama-3.1-8b-instant"]
_LIVE = None


def live_models(key, log=print):
    global _LIVE
    if _LIVE is None:
        try:
            r = requests.get("https://api.groq.com/openai/v1/models",
                             headers={"Authorization": f"Bearer {key}"}, timeout=20)
            ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True)] if r.status_code == 200 else []
            skip = ("whisper", "tts", "guard", "playai", "orpheus", "distil", "prompt-guard", "compound")
            ids = [i for i in ids if not any(x in i.lower() for x in skip)]
            order = [m for m in PREFERRED + MODELS if m in ids]
            order += sorted((i for i in ids if i not in order), key=lambda i: ("70b" not in i and "120b" not in i, i))
            _LIVE = list(dict.fromkeys(order))[:5] or list(dict.fromkeys(PREFERRED + MODELS))
            log(f"Groq live models: {', '.join(_LIVE)}")
        except Exception as e:
            log(f"Groq model list fail: {str(e)[:120]}")
            _LIVE = list(dict.fromkeys(PREFERRED + MODELS))
    return _LIVE


def ask_json(prompt, temp=0.8, log=print):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY nahi")
    last = None
    for model in live_models(key, log):
        body = {"model": model, "temperature": min(float(temp), 1.0), "max_tokens": 8000,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": "Reply with valid JSON only."},
                             {"role": "user", "content": prompt}]}
        if model.startswith("openai/"):
            body["reasoning_effort"] = "low"
        for attempt in range(2):
            try:
                r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                                  headers={"Authorization": f"Bearer {key}"}, json=body, timeout=120)
                if r.status_code != 200:
                    raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
                txt = r.json()["choices"][0]["message"]["content"]
                data = json.loads(txt)
                log(f"Groq model: {model}")
                return data
            except Exception as e:
                last = e
                log(f"groq {model} try {attempt + 1} failed: {str(e)[:200]}")
                if str(e).startswith(("404", "400")) and "model" in str(e).lower():
                    break   # yeh model band hai - agla model
                wait = re.search(r"try again in ([\d.]+)s", str(e))
                time.sleep(min(30.0, float(wait.group(1)) + 1) if wait else 3)
    raise RuntimeError(f"Groq fail: {last}")
