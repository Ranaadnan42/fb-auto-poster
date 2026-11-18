"""Gemma fallback ke liye Gemini requests theek karta hai (har agent `import gemfix` karta hai).

Free tier par har project ki roz ki limit (Nov 2026, AI Studio):
  Gemini Flash (3.8 / 3.6 / 3)  -> 20 / din     (5 / minute)
  Gemini Flash Lite (3.5 / 3.1) -> 500 / din    (15 / minute)
  Gemma 4 (31B / 26B)           -> 14,400 / din (30 / minute)
Is liye har agent ki model list ke aakhir mein Gemma 4 hai - Flash khatam ho to kaam nahi rukta.

Gemma JSON mode (responseMimeType) aur systemInstruction alag tarah leta hai, is liye
gemma model par: woh settings hata kar prompt mein likh deta hai, aur jawab se ```json``` wagaira
saaf kar ke sirf JSON wapas deta hai - taake purana code (json.loads) bina badle chale.
Requests (REST) aur google-genai SDK dono ko cover karta hai. Koi masla ho to chup chaap kuch nahi karta.
"""
import json
import re

GEMMA_MODELS = ["gemma-4-31b-it", "gemma-4-26b-a4b-it"]
_JSON_NOTE = "\n\nReply with ONLY valid JSON. No markdown, no ``` fences, no extra text."


def _clean_json_text(t):
    if not isinstance(t, str):
        return t
    s = t.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1).strip()
    starts = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    if starts:
        a = min(starts)
        b = max(s.rfind("}"), s.rfind("]"))
        if b > a:
            s = s[a:b + 1]
    return s


def _si_text(si):
    if isinstance(si, str):
        return si
    if isinstance(si, dict):
        return " ".join(p.get("text", "") for p in si.get("parts", []) if isinstance(p, dict))
    return ""


# ---------------------------------------------------------------- REST (requests)
try:
    import requests as _rq

    _orig_request = _rq.Session.request

    def _patched_request(self, method, url, *a, **kw):
        body = kw.get("json")
        gemma = (isinstance(url, str) and "generativelanguage.googleapis.com" in url
                 and "/models/gemma" in url and isinstance(body, dict))
        want_json = False
        if gemma:
            try:
                body = dict(body)
                gc = dict(body.get("generationConfig") or {})
                want_json = gc.pop("responseMimeType", None) == "application/json"
                for k in ("responseSchema", "responseJsonSchema", "thinkingConfig"):
                    gc.pop(k, None)
                body["generationConfig"] = gc
                si = body.pop("systemInstruction", None) or body.pop("system_instruction", None)
                extra = (_si_text(si) + "\n\n") if si else ""
                contents = [dict(c) for c in (body.get("contents") or [])]
                if contents and (extra or want_json):
                    parts = [dict(p) for p in contents[0].get("parts", [])]
                    tp = next((p for p in parts if "text" in p), None)
                    if tp is not None:
                        tp["text"] = extra + tp["text"] + (_JSON_NOTE if want_json else "")
                    else:
                        parts.insert(0, {"text": extra + (_JSON_NOTE if want_json else "")})
                    contents[0]["parts"] = parts
                    body["contents"] = contents
                kw["json"] = body
            except Exception:
                want_json = False
        r = _orig_request(self, method, url, *a, **kw)
        if gemma:
            try:
                j = r.json()
                for c in j.get("candidates", []):
                    parts = [p for p in c.get("content", {}).get("parts", []) if not p.get("thought")]
                    if want_json:
                        for p in parts:
                            if "text" in p:
                                p["text"] = _clean_json_text(p["text"])
                    c.setdefault("content", {})["parts"] = parts
                r._content = json.dumps(j).encode()
            except Exception:
                pass
        return r

    _rq.Session.request = _patched_request
except Exception:
    pass


# ---------------------------------------------------------------- google-genai SDK
try:
    from google.genai import models as _gm

    _orig_gc = _gm.Models.generate_content

    def _patched_gc(self, *a, **kw):
        model = kw.get("model") or (a[0] if a else "")
        if not str(model).split("/")[-1].startswith("gemma"):
            return _orig_gc(self, *a, **kw)
        want_json = False
        try:
            cfg = kw.get("config")
            si = None
            if cfg is not None:
                if isinstance(cfg, dict):
                    cfg = dict(cfg)
                    want_json = cfg.pop("response_mime_type", None) == "application/json"
                    cfg.pop("response_schema", None)
                    cfg.pop("thinking_config", None)
                    si = cfg.pop("system_instruction", None)
                else:
                    want_json = getattr(cfg, "response_mime_type", None) == "application/json"
                    si = getattr(cfg, "system_instruction", None)
                    cfg = cfg.model_copy(update={"response_mime_type": None, "response_schema": None,
                                                 "system_instruction": None, "thinking_config": None})
                kw["config"] = cfg
            extra = (si if isinstance(si, str) else "") + ("\n\n" if isinstance(si, str) else "")
            note = _JSON_NOTE if want_json else ""
            contents = kw.get("contents") if "contents" in kw else (a[1] if len(a) > 1 else None)
            if isinstance(contents, str):
                contents = extra + contents + note
            elif isinstance(contents, list) and contents and isinstance(contents[0], str):
                contents = [extra + contents[0] + note] + contents[1:]
            elif isinstance(contents, list) and (extra or note):
                contents = ([extra] if extra else []) + contents + ([note] if note else [])
            if "contents" in kw:
                kw["contents"] = contents
            elif len(a) > 1:
                a = (a[0], contents) + tuple(a[2:])
        except Exception:
            pass
        res = _orig_gc(self, *a, **kw)
        if want_json:
            try:
                for c in res.candidates or []:
                    for p in (c.content.parts or []):
                        if getattr(p, "text", None):
                            p.text = _clean_json_text(p.text)
            except Exception:
                pass
        return res

    _gm.Models.generate_content = _patched_gc
except Exception:
    pass
