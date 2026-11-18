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
try:  # Gemma 4 fallback (free 14,400/din) ke liye Gemini requests theek karta hai - gemfix.py
    import sys as _gf_sys, os as _gf_os
    _gf_dir = _gf_os.path.dirname(_gf_os.path.abspath(__file__))
    _gf_sys.path[:0] = [p for p in (_gf_dir, _gf_os.path.dirname(_gf_dir)) if p not in _gf_sys.path]
    import gemfix  # noqa: F401,E402
except Exception:
    pass
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
  Mobile app: PKR 60,000 | SAR/AED 4,000 | $700. POS one-time: PKR 20,000 | SAR/AED 600.
- Business website: clean, fast, professional, mobile friendly.
- Online store (e-commerce): customers order 24/7, cart, payments, delivery.
- Mobile app: custom Android apps - online ordering, delivery, booking, owner dashboard.
- POS software (Web Builder POS / cashier system): fast billing, barcode, live stock & inventory, daily sales & profit
  reports, works offline, one-time price with no monthly fee. Used by shops in Saudi Arabia, UAE and Pakistan.
- Works for every business: restaurant, grocery, supermarket, pharmacy, clothing, salon, school, clinic, bakery...
- Discount: never give or promise any discount yourself. If they ask for a discount or a lower price, politely say
  discount ki baat Web Builder team se WhatsApp par karein - they decide.
- Web Builder AutoPilot (AI auto system / AI employee): runs a business's social media by itself - makes and posts
  daily videos, reels and photos on Facebook, Instagram, YouTube and TikTok, replies to comments and messages,
  and finds new customers automatically, 24/7. The owner just runs the business.
- Demo: the Web Builder team shows a live demo on WhatsApp. Contact: WhatsApp."""

STATS = {"started": None, "loops": 0, "replies": 0, "likes": 0, "hidden": 0, "errors": [], "log": []}

# ---------------------------------------------------------------- AGENT memory
# Comment agent ki yaad (repo mein save): har page par kaun aksar comment karta hai, kis zubaan mein, kya poochha;
# aur har page ke liye agent ke khud seekhe hue sabaq (har ~3 ghante pichli baat-cheet dekh kar).
MEM_FILE = "comment_agent_memory.json"
REVIEW_EVERY = 3 * 3600
CONVOS = {}        # page -> is run ki baat-cheet (sabaq seekhne ke liye)


def load_mem():
    try:
        with open(MEM_FILE, encoding="utf-8") as f:
            m = json.load(f)
    except Exception:
        m = {}
    m.setdefault("pages", {})
    return m


MEM = load_mem()


def page_mem(acct):
    p = MEM["pages"].setdefault(acct, {})
    p.setdefault("fans", {})
    p.setdefault("lessons", [])
    p.setdefault("last_review", 0)
    return p


def remember_fan(acct, uid, name, text, action):
    if not uid:
        return
    fans = page_mem(acct)["fans"]
    f = fans.setdefault(uid, {"name": name, "count": 0, "notes": []})
    f["name"] = name or f.get("name", "")
    f["count"] += 1
    f["last"] = now().isoformat()[:16]
    f["notes"] = (f["notes"] + [f"{action}: {text[:70]}"])[-4:]
    if len(fans) > 400:            # sab se purane fans hata do - file halki rahe
        for k in sorted(fans, key=lambda k: fans[k].get("last", ""))[:len(fans) - 400]:
            fans.pop(k, None)


def fan_line(acct, uid):
    f = page_mem(acct)["fans"].get(uid or "")
    if not f or f.get("count", 0) < 1:
        return "This is a NEW commenter (first time we talk to them)."
    return (f"RETURNING fan \"{f.get('name', '')}\" - talked {f['count']} times before. Earlier: "
            + " | ".join(f.get("notes", [])) + ". Greet them like a regular (e.g. welcome back), don't repeat old replies.")


def review(acct):
    """Agent khud seekhta hai: is page par log kya poochte/kehte hain aur kaise jawab se baat aage barhi."""
    pm = page_mem(acct)
    convos = CONVOS.get(acct) or []
    if time.time() - pm["last_review"] < REVIEW_EVERY or len(convos) < 3:
        return
    pm["last_review"] = time.time()
    name = PERSONA[acct][0]
    try:
        d = ask(acct=acct, prompt=f"""You are the comment-manager AI agent of the Facebook page "{name}". Below are recent comment
conversations (C = commenter, P = page). Learn from them. Note what people ask/feel most, which replies got the
commenter to write again (good), which got no answer, and what spam appears.
Current lessons: {json.dumps(pm["lessons"], ensure_ascii=False)}
Conversations:
{chr(10).join(convos[-40:])[-6000:]}

Return JSON {{"lessons": ["max 6 short, concrete rules for future replies on THIS page, keep the still-true current ones"]}}""")
        les = [str(x)[:200] for x in (d.get("lessons") or []) if str(x).strip()][:6]
        if les:
            pm["lessons"] = les
            log(f"{acct}: agent ne naye sabaq seekhe: {les}")
        CONVOS[acct] = convos[-10:]
    except Exception as e:
        log(f"{acct} review fail: {str(e)[:150]}")


def save_mem():
    with open(MEM_FILE, "w", encoding="utf-8") as f:
        json.dump(MEM, f, ensure_ascii=False, indent=1)
SKIP = set()       # jin messages par AI ne jawab na dena chuna (spam/gaali) - dobara na poochhe


def now():
    return dt.datetime.now(dt.timezone.utc)


def age_hours(ts):
    try:
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+0000", "+00:00"))
        return (now() - t).total_seconds() / 3600
    except Exception:
        return 0


# Naye pages ki apni alag API keys - purani (shared) keys in par kabhi nahi lagti
OWN_KEYS = {"newsur": "NEWSUR", "wild": "WILD", "birds": "BIRDS", "pets": "PETS", "war": "WAR"}


def own_ready(acct):
    p = OWN_KEYS.get(acct)
    return not p or bool(env(f"{p}_GEMINI_API_KEY") or env(f"{p}_GROQ_API_KEY"))


def ask_own(prompt, p):
    import requests
    gk, qk = env(f"{p}_GEMINI_API_KEY"), env(f"{p}_GROQ_API_KEY")
    if qk:
        old = os.environ.get("GROQ_API_KEY")
        os.environ["GROQ_API_KEY"] = qk
        try:
            return groq_backup.ask_json(prompt, 0.7, log)
        except Exception as e:
            log(f"{p} groq fail: {str(e)[:120]}")
        finally:
            if old is None:
                os.environ.pop("GROQ_API_KEY", None)
            else:
                os.environ["GROQ_API_KEY"] = old
    if not gk:
        raise RuntimeError(f"{p}: apni API key nahi")
    for model in ("gemini-3.8-flash", "gemini-3-flash-preview", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemma-4-31b-it", "gemma-4-26b-a4b-it"):
        try:
            j = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              params={"key": gk}, timeout=90,
                              json={"contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}}).json()
            return json.loads(j["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            log(f"{p} gemini {model} fail: {str(e)[:100]}")
    raise RuntimeError(f"{p}: AI jawab nahi")


def ask(prompt, acct=None):
    """Tez jawab ke liye pehle Groq, phir Gemini. Naye pages (OWN_KEYS) sirf apni keys se."""
    if acct in OWN_KEYS:
        return ask_own(prompt, OWN_KEYS[acct])
    if groq_backup.enabled():
        try:
            return groq_backup.ask_json(prompt, 0.7, log)
        except Exception as e:
            log(f"groq fail: {str(e)[:120]}")
    return growth.ask_json(prompt)


AI_CHAT = "https://fobzocsluzwcqretshnm.supabase.co/functions/v1/ai-chat"
SITE = "https://client-hunt-six.vercel.app/"


def lang_of(text):
    import re
    if re.search(r"[\u0600-\u06FF]", text):
        urdu = re.search(r"[\u0679\u0688\u0691\u06BA\u06BE\u06C1\u06D2\u067E\u0686\u0698\u06AF]", text)
        return "URDU (Urdu script)" if urdu else "ARABIC"
    roman_urdu = re.search(r"\b(kya|kia|hai|hain|ki|ka|ke|mein|ma|mera|meri|aap|ap|kitne|kitna|chahiye|"
                           r"krna|karna|bhai|sakte|ho|nahi|ni|kaise|ksy|dikha)\b", text.lower())
    return "ROMAN URDU (Urdu words in English/Latin letters, NOT Urdu script)" if roman_urdu else "the customer's language"


def wb_brain(post_text, thread, first):
    """Web Builder: wahi sales brain jo website chat aur email bot use karte hain (ai-chat) -
    ek hi price list, aur garam customer par Rana ko email/WhatsApp alert."""
    import re
    import requests
    msgs = [{"role": "assistant" if m["page"] else "user", "content": m["text"]} for m in thread]
    while msgs and msgs[0]["role"] == "assistant" and len(msgs) > 1 and msgs[1]["role"] == "assistant":
        msgs.pop(0)
    ctx = (f"[FACEBOOK COMMENT CHANNEL. The customer commented under our Facebook post: \"{post_text[:200]}\". "
           "Reply as a Facebook comment: 1-3 short sentences, max 50 words, no markdown, no bullet points. "
           f"LANGUAGE: reply in {lang_of(thread[-1]['text'])} - exactly the language and script the customer "
           "wrote in, even if their city is in another country.]\n\n")
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


def write_reply(acct, post_text, thread, page_name, first, uid=""):
    if acct == "webbuilder":
        try:
            r = wb_brain(post_text, thread, first)
            return {"action": "reply" if r else "skip", "reply": r}
        except Exception as e:
            log(f"ai-chat fail, apna AI: {str(e)[:150]}")
    name, style = PERSONA[acct]
    lessons = page_mem(acct)["lessons"]
    lessons = ("What you (the agent) learned on this page:\n- " + "\n- ".join(lessons) + "\n") if lessons else ""
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
    data = ask(acct=acct, prompt=f"""You reply on Facebook as the page "{name}". Style: {style}
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
- You are this page's AI comment AGENT, not a bot: think about the person, what they really mean, and the page's
  growth. Where natural, end with ONE short friendly question so they comment again (more comments = more reach),
  but not on every reply and never on spam.
{lessons}
About this person: {fan_line(acct, uid)}

Also decide the ACTION:
- "reply": normal reply (also "like" their comment).
- "like": only a like, no text (e.g. they just tagged a friend, or a bare emoji after we already thanked them).
- "hide": spam, scam, abuse, gaali, someone else's promotion or links - hide it from the page.
- "skip": nothing to do.
Return JSON: {{"action": "reply|like|hide|skip", "reply": "...", "contact": true/false}}""")
    reply = (data.get("reply") or "").strip()[:900]
    action = (data.get("action") or ("reply" if reply else "skip")).strip().lower()
    if action != "reply":
        return {"action": action, "reply": ""}
    if reply and acct == "webbuilder" and (first or data.get("contact")):
        reply = growth.add_footer("webbuilder", reply)
    return {"action": "reply" if reply else "skip", "reply": reply}


def threads_for(acct):
    pid, token = (env(k) for k in FB_ACCOUNTS[acct])
    import fbtoken
    token = fbtoken.page_token(pid, token)
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
                       "uid": (m.get("from") or {}).get("id", ""), "name": (m.get("from") or {}).get("name", ""),
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
        if not own_ready(acct):
            continue          # naya page: apni API key abhi nahi lagi
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
                dec = write_reply(acct, t["post"], t["thread"], acct, t["first"], last.get("uid", ""))
            except Exception as e:
                log(f"{acct} AI fail: {str(e)[:150]}")
                continue
            reply, action = dec.get("reply") or "", dec.get("action")
            CONVOS.setdefault(acct, []).append(
                " / ".join(f"{'P' if m['page'] else 'C'}: {m['text'][:120]}" for m in t["thread"][-4:])
                + f" -> agent {action}: {reply[:120]}")
            remember_fan(acct, last.get("uid"), last.get("name"), last["text"], action)
            if action in ("like", "hide") and not DRY_RUN:
                try:
                    if action == "like":
                        fb_call("POST", f"{last['id']}/likes", token)
                        STATS["likes"] += 1
                    else:
                        fb_call("POST", last["id"], token, is_hidden="true")
                        STATS["hidden"] += 1
                    log(f"{acct}: {action} {last['text'][:50]!r}")
                except Exception as e:
                    log(f"{acct} {action} fail: {str(e)[:120]}")
            if not reply:
                SKIP.add(last["id"])
                continue
            if DRY_RUN:
                log(f"[dry] {acct}: {last['text'][:60]!r} -> {reply[:120]}")
                SKIP.add(last["id"])
            else:
                try:
                    fb_call("POST", f"{t['top']}/comments", token, message=reply)
                    try:
                        fb_call("POST", f"{last['id']}/likes", token)      # jawab ke saath comment like bhi
                        STATS["likes"] += 1
                    except Exception:
                        pass
                except Exception as e:
                    log(f"{acct} post fail: {str(e)[:150]}")
                    SKIP.add(last["id"])
                    continue
            STATS["replies"] += 1
            line = f"{now():%m-%d %H:%M} {acct}: {last['text'][:50]!r} -> {reply.splitlines()[0][:90]}"
            STATS["log"] = (STATS["log"] + [line])[-60:]
            log(line)
        review(acct)


def save():
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(STATS, f, ensure_ascii=False, indent=1)
    save_mem()


def main():
    STATS["started"] = now().isoformat()
    test = os.environ.get("TEST_TEXT")
    if test:      # self-test: ek nakli comment par Web Builder ka jawab
        for q in test.split("||"):
            r = write_reply("webbuilder", "POS software for shops", [{"page": False, "text": q, "id": "t", "time": ""}],
                            "webbuilder", True).get("reply")
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
