"""
Har bot run ke shuru mein chalta hai:
1. Agar is post ke liye pehle se koi run chal raha / ho chuka hai -> yeh run kuch nahi karta (double post nahi).
2. Agar GitHub ne run bohat jaldi chala diya (post 5.5 ghante se zyada door) -> yahan intezar,
   taake video job ki 6 ghante ki hadd mein theek post waqt par jaye (pehle post nahi).
Hath se chalaya (sched khali) -> hamesha chalta hai.
"""
import os
import sys
import time
import datetime

sys.path.insert(0, os.path.dirname(__file__))
import slots      # noqa: E402
import ghapi      # noqa: E402

FILE = os.environ["WF_FILE"]
SCHED = (os.environ.get("SCHED") or "").strip()
RUN_ID = int(os.environ.get("GITHUB_RUN_ID") or 0)
EVENT = os.environ.get("GITHUB_EVENT_NAME", "")
MAX_EARLY_MIN = 330          # build job post se zyada se zyada itne minute pehle shuru ho


def out(go, why):
    print(why)
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write(f"go={'true' if go else 'false'}\n")
    sys.exit(0)


def earlier_run(slot, p):
    since = p - datetime.timedelta(hours=slots.WINDOW_H)
    for r in ghapi.slot_runs(slot, since, exclude_id=RUN_ID):
        if r["id"] < RUN_ID and r.get("conclusion") not in ("cancelled", "skipped"):
            return r
    return None


if not SCHED:
    out(True, "Hath se chalaya - koi rok nahi")

slot = slots.find(FILE, SCHED)
if not slot:
    out(True, f"{SCHED} table mein nahi - chalne do")

now = ghapi.utcnow()
p = ghapi.post_dt(slot["post"], now)
print(f"Post waqt {p:%Y-%m-%d %H:%M} UTC, abhi {now:%H:%M} UTC")

try:
    r = earlier_run(slot, p)
except Exception as e:                       # API na chale to post na rukay
    out(True, f"Check nahi ho saka ({e}) - chalne do")
if r:
    out(False, f"Is post ka run pehle se hai ({r['html_url']}) - yeh run chhor diya")

early = (p - now).total_seconds() / 60 - MAX_EARLY_MIN
if early > 0:
    print(f"Run bohat jaldi chala - {int(early)} minute intezar")
    time.sleep(early * 60)
    try:
        r = earlier_run(slot, p)
    except Exception:
        r = None
    if r:
        out(False, f"Is post ka run pehle se hai ({r['html_url']}) - yeh run chhor diya")

out(True, "Chalo - video banao")
