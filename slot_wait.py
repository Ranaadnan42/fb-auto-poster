"""
Post ko theek selected waqt par bhejne ke liye.

GitHub ke scheduled runs aksar 0-6 ghante late chalte hain. Is liye workflow
post se ~5.5 ghante pehle schedule hai, video pehle se ban jati hai, aur post
karne se pehle yahan intezar hota hai jab tak POST_AT (UTC "HH:MM") na aa jaye.
Job ki 6 ghante ki hadd (JOB_START se SLOT_BUDGET_MIN minute) tak hi intezar
hota hai - us se aage ho to hadd par post. Waqt guzar chuka ho to foran post.
POST_AT khali ho (hath se chalaya) to koi intezar nahi.
"""
import os
import time
import datetime

_done = False
_START = float(os.environ.get("JOB_START") or time.time())
BUDGET_MIN = float(os.environ.get("SLOT_BUDGET_MIN") or 335)   # job start se itne minute tak intezar


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
    limit = datetime.datetime.utcfromtimestamp(_START + BUDGET_MIN * 60)
    if t > limit:                                         # job 6 ghante se zyada nahi chal sakti
        log(f"Post waqt {t:%H:%M} job ki hadd se aage - {limit:%H:%M} UTC par post hogi")
        t = limit
        secs = (t - datetime.datetime.utcnow()).total_seconds()
        if secs <= 0:
            return
    log(f"Video tayyar - {int(secs // 60)} minute intezar, post {t:%H:%M} UTC par hogi")
    while True:
        secs = (t - datetime.datetime.utcnow()).total_seconds()
        if secs <= 0:
            break
        time.sleep(min(secs, 300))
    log("Waqt ho gaya - post kar rahe hain")
