"""
YouTube channel ko comment/playlist ijazat (youtube.force-ssl) ke saath dobara connect karna.
  STEP=start  -> Google ka permission link bana kar 'yt-connect' branch par connect_<account>.txt mein rakhta hai
  STEP=finish -> CODE (permission ke baad wapas aaya code) se refresh token le kar yt_tokens/<account>.enc
                 (encrypted) mein save karta hai. Purane upload tokens ko haath nahi lagta.
"""
import os
import sys
import json
import urllib.parse

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yt_tokens  # noqa: E402

PREFIX = {"legends": "YT", "world": "YT_WORLD", "frames": "YT_FRAMES", "islamic": "YT_ISLAMIC",
          "funny": "YT_FUNNY", "movie": "YT_MOVIE"}
REDIRECT = "http://127.0.0.1:8765/"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl"

acct = os.environ["ACCOUNT"].strip().lower()
p = PREFIX[acct]
cid = os.environ.get(f"{p}_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
sec = os.environ.get(f"{p}_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
if not (cid and sec):
    sys.exit(f"{acct}: client id/secret secrets nahi mile")

if os.environ["STEP"] == "start":
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent select_account", "state": acct})
    os.makedirs("connect_out", exist_ok=True)
    open(f"connect_out/connect_{acct}.txt", "w").write(url + "\n")
    print("Permission link bana diya (yt-connect branch)")
else:
    code = urllib.parse.unquote((os.environ.get("CODE") or "").strip())
    j = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "code": code, "client_id": cid, "client_secret": sec, "redirect_uri": REDIRECT,
        "grant_type": "authorization_code"}).json()
    if "refresh_token" not in j:
        sys.exit(f"token nahi mila: {json.dumps({k: v for k, v in j.items() if 'token' not in k})}")
    if "youtube.force-ssl" not in j.get("scope", ""):
        sys.exit(f"comment ijazat nahi di gayi (scope: {j.get('scope')})")
    ch = requests.get("https://www.googleapis.com/youtube/v3/channels", timeout=60,
                      params={"part": "snippet", "mine": "true"},
                      headers={"Authorization": f"Bearer {j['access_token']}"}).json()
    title = (ch.get("items") or [{}])[0].get("snippet", {}).get("title", "?")
    print(f"Connected channel: {title}")
    yt_tokens.save(acct, j["refresh_token"], sec)
    print(f"yt_tokens/{acct}.enc saved")
