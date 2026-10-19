"""
Post ko theek selected waqt par bhejne ke liye.

GitHub ke scheduled runs aksar 1-5 ghante late chalte hain. Is liye workflow
ab ~5 ghante pehle chalta hai, video pehle se ban jati hai, aur post karne se
pehle yahan intezar hota hai jab tak POST_AT (UTC "HH:MM") ka waqt na aa jaye.
Agar run waise hi late ho (waqt guzar chuka) to foran post hoti hai.
POST_AT khali ho (hath se chalaya) to koi intezar nahi.
"""
import os
import time
import datetime

_done = False


def target_time():
    """Aaj ka post waqt (UTC datetime) ya None."""
    val = (os.environ.get("POST_AT") or "").strip()
    if not val:
        return None
    try:
        hh, mm = (int(x) for x in val.split(":"))
    except ValueError:
        return None
    now = datetime.datetime.utcnow()
    t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if (t - now).total_seconds() > 12 * 3600:
        t -= datetime.timedelta(days=1)
    elif (now - t).total_seconds() > 12 * 3600:
        t += datetime.timedelta(days=1)
    return t


def wait(log=print):
    global _done
    if _done:
        return
    _done = True
    t = target_time()
    if t is None:
        return
    secs = (t - datetime.datetime.utcnow()).total_seconds()
    if secs <= 0:
        log(f"Post waqt {t:%H:%M} UTC guzar chuka - foran post")
        return
    if secs > 120 * 60:                                   # GitHub par ghanton khali na baithein
        log(f"Post waqt bahut door ({int(secs // 60)} min) - foran post")
        return
    log(f"Video tayyar - {int(secs // 60)} minute intezar, post {t:%H:%M} UTC par hogi")
    while True:
        secs = (t - datetime.datetime.utcnow()).total_seconds()
        if secs <= 0:
            break
        time.sleep(min(secs, 300))
    log("Waqt ho gaya - post kar rahe hain")
