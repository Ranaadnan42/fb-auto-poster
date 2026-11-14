"""User token mila ho to usi page ka (kabhi expire na hone wala) PAGE token bana deta hai.
Long-lived user token se bana page token expire nahi hota. Sab agents yahi istemal karein."""
import requests

GRAPH = "https://graph.facebook.com/v23.0"
_CACHE = {}


def page_token(pid, token):
    if not (pid and token):
        return token
    key = (pid, token[-12:])
    if key in _CACHE:
        return _CACHE[key]
    out = token
    try:
        me = requests.get(f"{GRAPH}/me", params={"fields": "id", "access_token": token}, timeout=30).json()
        if me.get("id") != pid:
            pt = requests.get(f"{GRAPH}/{pid}", params={"fields": "access_token", "access_token": token},
                              timeout=30).json().get("access_token")
            if pt:
                out = pt
    except Exception:
        pass
    _CACHE[key] = out
    return out
