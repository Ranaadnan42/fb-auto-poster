"""
Live Replies - Facebook pages par comment aate hi (har ~1 minute) jawab, aur poori baat-cheet.

- Har page ki nayi posts ke comments + un ke andar replies (thread) dekhta hai.
- Agar thread mein AAKHRI baat customer ki hai (page ki nahi) to poori baat-cheet parh kar
  usi zubaan mein jawab deta hai. Customer phir likhe to phir jawab - baat chalti rehti hai.
- Web Builder: salesman ki tarah - website / app / POS ke sawalon ka jawab, customer ko
  WhatsApp aur website par laata hai. Pehle jawab (aur jab contact chahiye) ke neeche
  website link + WhatsApp.
- Kisi comment ka jawab diya ya nahi, FB se hi pata chalta hai (thread mein aakhri kaun) - alag yaad nahi chahiye.

GitHub Actions mein ~5 ghante 50 minute lagatar chalta hai, phir agla run shuru (live.yml).
Env: page ids/tokens (growth.py wale), GROQ_API_KEY (pehle - tez), GEMINI_API_KEY (backup)
     LIVE_MINUTES (default 345), POLL_SECONDS (default 60), DRY_RUN=1
"""
import os
import json
import time
import datetime as dt

import growth
import groq_backup
from growth import PERSONA, FB_ACCOUNTS, fb_call, env, log

LIVE_MINUTES = float(os.environ.get("LIVE_MINUTES") or 345)
POLL = int(os.environ.get("POLL_SECONDS") or 12)        # Web Builder har ~12 second
OTHERS_EVERY = int(os.environ.get("OTHERS_SECONDS") or 45)  # baqi pages har ~45 second
PAUSE = {}          # page -> kab tak ruke (Facebook rate limit par)
DRY_RUN = os.environ.get("DRY_RUN") == "1"
MAX_AGE_HOURS = 72          # is se purani customer baat ka jawab nahi
POSTS = 25
REPORT_FILE = "live_last_run.json"

WB_FACTS = """- Prices "starting from" in the customer's region:
  Website: Pakistan PKR 15,000 | Saudi/UAE SAR/AED 400 | world $150. Online store: PKR 60,000 | SAR/AED 2,500 | $900.
  Mobile app: PKR 60,000 | SAR/AED 4,000 | $700. POS one-time: PKR 15,000 | SAR/AED 600.
- Business website: clean, fast, professional, mobile friendly.
- Online store (e-commerce): customers order 24/7, cart, payments, delivery.
- Mobile app: custom Android apps - online ordering, delivery, booking, owner dashboard.
- POS software (Rana POS / cashier system): fast billing, barcode, live stock & inventory, daily sales & profit
  reports, works offline, one-time price with no monthly fee. Used by shops in Saudi Arabia, UAE and Pakistan.
- Works for every business: restaurant, grocery, supermarket, pharmacy, clothing, salon, school, clinic, bakery...
- Demo: Rana shows a live demo on WhatsApp. Contact: WhatsApp."""

STATS = {"started": None, "loops": 0, "replies": 0, "errors": [], "log": []}
SKIP = set()       # jin messages par AI ne jawab na dena chuna (spam/gaali) - dobara na poochhe


def now():
    return dt.datetime.now(dt.timezone.utc)


def age_hours(ts):
    try:
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+0000", "+00:00"))
        return (now() - t).total_seconds() / 3600
    except Exception:
        return 0


def ask(prompt):
    """Tez jawab ke liye pehle Groq, phir Gemini."""
    if groq_backup.enabled():
        try:
            return groq_backup.ask_json(prompt, 0.7, log)
        except Exception as e:
            log(f"groq fail: {str(e)[:120]}")
    return growth.ask_json(prompt)


AI_CHAT = "https://fobzocsluzwcqretshnm.supabase.co/functions/v1/ai-chat"
SITE = "https://client-hunt-six.vercel.app/"


def wb_brain(post_text, thread, first):
    """Web Builder: wahi sales brain jo website chat aur email bot use karte hain (ai-chat) -
    ek hi price list, aur garam customer par Rana ko email/WhatsApp alert."""
    import re
    import requests
    msgs = [{"role": "assistant" if m["page"] else "user", "content": m["text"]} for m in thread]
    while msgs and msgs[0]["role"] == "assistant" and len(msgs) > 1 and msgs[1]["role"] == "assistant":
        msgs.pop(0)
    ctx = (f"[FACEBOOK COMMENT CHANNEL. The customer commented under our Facebook post: \"{post_text[:200]}\". "
           "Reply as a Facebook comment: 1-3 short sentences, max 50 words, in the customer's own language and "
           "script, no markdown, no bullet points.]\n\n")
    msgs[-1] = {"role": "user", "content": ctx + msgs[-1]["content"]}
    r = requests.post(AI_CHAT, json={"messages": msgs, "channel": "facebook"}, timeout=45)
    reply = (r.json().get("reply") or "").strip()
    reply = re.sub(r"\*\*|__|^#+ ", "", reply, flags=re.M).strip()[:900]
    if not reply:
        raise RuntimeError(f"ai-chat empty: {r.text[:150]}")
    if first and "5267349" not in reply:
        reply = growth.add_footer("webbuilder", reply)
    elif "client-hunt" not in reply and ("5267349" in reply or first):
        reply += f"\n\U0001F310 {SITE}"
    return reply


def write_reply(acct, post_text, thread, page_name, first):
    if acct == "webbuilder":
        try:
            return wb_brain(post_text, thread, first)
        except Exception as e:
            log(f"ai-chat fail, apna AI: {str(e)[:150]}")
    name, style = PERSONA[acct]
    sales = ""
    if acct == "webbuilder":
        sales = f"""You are the sales person of Web Builder. Talk like a helpful human salesman: answer the question,
explain the benefit in simple words, ask ONE short question to understand their business (shop type, country,
what they need) and move them towards WhatsApp for price/demo/order.
Facts you may use (NEVER invent other prices, discounts, delivery times or guarantees):
{WB_FACTS}
Do NOT write the website link or WhatsApp number yourself - set "contact": true and they are added below.
Set "contact": true when they ask price, demo, order, contact, location, or are ready to buy."""
    convo = "\n".join(f"{'PAGE (you)' if m['page'] else 'CUSTOMER'}: {m['text']}" for m in thread)
    data = ask(f"""You reply on Facebook as the page "{name}". Style: {style}
{sales}
Post: "{post_text[:300]}"
Conversation so far under this post (oldest first):
{convo[-3000:]}

Write the page's next reply to the CUSTOMER's last message.
Rules:
- Same language and script the customer used (Urdu script, Roman Urdu, English, Arabic, Hindi...).
- Short and human: 1-3 sentences, max 45 words. Respond to what they actually said, don't repeat earlier replies.
- Short praise like "MashaAllah", "nice", "😂", "❤️" still gets a warm short thank-you reply.
- No hashtags. No links.
- If the message is spam, abuse, someone else's promotion/link, return reply "".
Return JSON: {{"reply": "...", "contact": true/false}}""")
    reply = (data.get("reply") or "").strip()[:900]
    if reply and acct == "webbuilder" and (first or data.get("contact")):
        reply = growth.add_footer("webbuilder", reply)
    return reply


def threads_for(acct):
    pid, token = (env(k) for k in FB_ACCOUNTS[acct])
    if not (pid and token):
        return None, None, []
    sub = "comments.limit(25){id,from,message,created_time}"
    posts = fb_call("GET", f"{pid}/feed", token, limit=POSTS,
                    fields=f"id,message,created_time,comments.limit(50).order(reverse_chronological)"
                           f"{{id,from,message,created_time,{sub}}}").get("data", [])
    out = []
    for p in posts:
        for c in (p.get("comments") or {}).get("data", []):
            msgs = [c] + list((c.get("comments") or {}).get("data", []))
            msgs = [m for m in msgs if (m.get("message") or "").strip()]
            if not msgs:
                continue
            msgs.sort(key=lambda m: m.get("created_time", ""))
            thread = [{"id": m["id"], "page": (m.get("from") or {}).get("id") == pid,
                       "text": m["message"].strip()[:500], "time": m.get("created_time", "")} for m in msgs]
            last = thread[-1]
            if last["page"] or last["id"] in SKIP or age_hours(last["time"]) > MAX_AGE_HOURS:
                continue
            out.append({"post": p.get("message") or "", "top": c["id"], "thread": thread,
                        "first": not any(m["page"] for m in thread)})
    return pid, token, out


def one_pass(accts):
    for acct in accts:
        if PAUSE.get(acct, 0) > time.time():
            continue
        try:
            pid, token, todo = threads_for(acct)
        except Exception as e:
            if "limit" in str(e).lower() or "(#4)" in str(e) or "(#32)" in str(e):
                PAUSE[acct] = time.time() + 300      # FB ne roka - 5 minute aaram
            msg = f"{acct}: {str(e)[:150]}"
            if msg not in STATS["errors"]:
                STATS["errors"].append(msg)
            log(msg)
            continue
        for t in todo[:10]:
            last = t["thread"][-1]
            try:
                reply = write_reply(acct, t["post"], t["thread"], acct, t["first"])
            except Exception as e:
                log(f"{acct} AI fail: {str(e)[:150]}")
                continue
            if not reply:
                SKIP.add(last["id"])
                continue
            if DRY_RUN:
                log(f"[dry] {acct}: {last['text'][:60]!r} -> {reply[:120]}")
                SKIP.add(last["id"])
            else:
                try:
                    fb_call("POST", f"{t['top']}/comments", token, message=reply)
                except Exception as e:
                    log(f"{acct} post fail: {str(e)[:150]}")
                    SKIP.add(last["id"])
                    continue
            STATS["replies"] += 1
            line = f"{now():%m-%d %H:%M} {acct}: {last['text'][:50]!r} -> {reply.splitlines()[0][:90]}"
            STATS["log"] = (STATS["log"] + [line])[-60:]
            log(line)


def save():
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(STATS, f, ensure_ascii=False, indent=1)


def main():
    STATS["started"] = now().isoformat()
    test = os.environ.get("TEST_TEXT")
    if test:      # self-test: ek nakli comment par Web Builder ka jawab
        for q in test.split("||"):
            r = write_reply("webbuilder", "POS software for shops", [{"page": False, "text": q, "id": "t", "time": ""}],
                            "webbuilder", True)
            STATS["log"].append(f"TEST {q!r} -> {r}")
            log(STATS["log"][-1])
        save()
        return
    end = time.time() + LIVE_MINUTES * 60
    last_others = 0
    others = [a for a in FB_ACCOUNTS if a != "webbuilder"]
    while True:
        t0 = time.time()
        accts = ["webbuilder"]
        if t0 - last_others >= OTHERS_EVERY:
            accts += others
            last_others = t0
        one_pass(accts)
        STATS["loops"] += 1
        STATS["last_check"] = now().isoformat()
        if STATS["loops"] % 30 == 1:
            save()
        if time.time() + POLL > end:
            break
        time.sleep(max(5, POLL - (time.time() - t0)))
    save()
    log(f"Done: {STATS['loops']} checks, {STATS['replies']} jawab")


if __name__ == "__main__":
    main()
