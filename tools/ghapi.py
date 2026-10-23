"""Chhota GitHub API helper (sirf Python ki standard library)."""
import os
import json
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error

REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")


def call(method, path, body=None, params=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise
        except Exception:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"GitHub API fail: {method} {path}")


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def runs_since(file, since):
    """Is workflow ke runs jo `since` (UTC datetime) ke baad bane."""
    out = call("GET", f"/actions/workflows/{file}/runs",
               params={"created": ">=" + iso(since), "per_page": 100})
    return out.get("workflow_runs", [])


def slot_runs(slot, since, exclude_id=None):
    """Is post (slot) ke runs - naam mein [cron] ho. Purane bina-naam ke schedule runs bhi gine jate hain."""
    res = []
    for r in runs_since(slot["file"], since):
        if exclude_id and r["id"] == exclude_id:
            continue
        title = r.get("display_title") or ""
        if any(f"[{c}]" in title for c in slot["crons"]):
            res.append(r)
        elif "[" not in title and r.get("event") == "schedule":
            res.append(r)          # naya naam lagne se pehle wale runs
    return res


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def post_dt(post, around):
    """`post` "HH:MM" ka woh waqt jo `around` ke sab se qareeb ho."""
    hh, mm = (int(x) for x in post.split(":"))
    base = around.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return min((base + datetime.timedelta(days=d) for d in (-1, 0, 1)),
               key=lambda t: abs((t - around).total_seconds()))
