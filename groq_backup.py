"""
Groq backup brain: jab Gemini ki daily limit (429) khatam ho jaye to yeh JSON jawab deta hai.
Secret: GROQ_API_KEY (na ho to kuch nahi karta - purana error hi aata hai).
"""
import json
import os
import time

import requests

MODELS = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"]


def enabled():
    return bool(os.environ.get("GROQ_API_KEY"))


def ask_json(prompt, temp=0.8, log=print):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY nahi")
    last = None
    for model in MODELS:
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
                time.sleep(3)
    raise RuntimeError(f"Groq fail: {last}")
