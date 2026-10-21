"""
Search demand - log YouTube par asal mein kya search karte hain (free, koi key nahi).

1. suggestions(): YouTube search box ke suggestions (wahi jo type karte waqt neeche aate hain).
   Yeh evergreen topic chunne mein madad karte hain - aisi video saalon search mein aati hai.
2. islamic_occasion(): har saal wapas aane wale mauqe (Jumma, Ramzan, Eid, Muharram...).

Kuch bhi fail ho (internet, block) to khali list / None - bot purane tareeqe se chalta rahe.
"""
import datetime

import requests

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"


def suggestions(seeds, lang="en", country="US", limit=20):
    """Har seed ke liye YouTube autocomplete. Wapas: unique phrases ki list (max limit)."""
    out, seen = [], set()
    for seed in seeds:
        if not seed:
            continue
        try:
            r = requests.get(SUGGEST_URL, params={"client": "firefox", "ds": "yt", "q": seed,
                                                  "hl": lang, "gl": country},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            items = r.json()[1] if r.status_code == 200 else []
        except Exception as e:
            print(f"[search] '{seed}' fail: {str(e)[:120]}", flush=True)
            items = []
        for s in items:
            s = (s or "").strip()
            if s and s.lower() not in seen and s.lower() != seed.lower():
                seen.add(s.lower())
                out.append(s)
    return out[:limit]


def _pk_today():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=5)


def islamic_occasion(now=None):
    """Aaj Pakistan mein koi Islamic mauqa hai? Wapas: (key, theme, seeds_en, seeds_ur) ya None.
    Hijri tareekh Umm al-Qura se (Pakistan mein 1 din ka farq ho sakta hai - is liye
    sirf lambe arsay wale mauqe aur Eid ke 3 din)."""
    now = now or _pk_today()
    try:
        from hijridate import Gregorian
        h = Gregorian(now.year, now.month, now.day).to_hijri()
        m, d = h.month, h.day
    except Exception as e:
        print(f"[search] hijri date fail: {str(e)[:120]}", flush=True)
        m = d = 0

    if m == 9:
        return ("ramadan", "Ramadan: fasting, Quran, forgiveness and Laylatul Qadr",
                ["ramadan", "ramadan reminder"], ["رمضان", "ramzan"])
    if m == 10 and d <= 3:
        return ("eid_fitr", "Eid ul Fitr: gratitude, joy and keeping good habits after Ramadan",
                ["eid ul fitr", "eid mubarak"], ["عید", "eid mubarak"])
    if m == 12 and d <= 9:
        return ("dhul_hijjah", "the first ten days of Dhul Hijjah, Hajj and the day of Arafah",
                ["dhul hijjah", "day of arafah"], ["ذوالحجہ", "hajj"])
    if m == 12 and 10 <= d <= 12:
        return ("eid_adha", "Eid ul Adha: the sacrifice and obedience of Prophet Ibrahim",
                ["eid ul adha", "qurbani"], ["عید الاضحی", "qurbani"])
    if m == 1 and d <= 10:
        return ("muharram", "the Islamic new year and the day of Ashura when Allah saved Prophet Musa",
                ["islamic new year", "ashura fasting"], ["محرم", "muharram"])
    if m == 3 and d <= 12:
        return ("seerah", "the life, mercy and character of Prophet Muhammad (Seerah)",
                ["prophet muhammad life", "seerah"], ["سیرت النبی", "nabi ki seerat"])
    if m == 7 and 25 <= d <= 27:
        return ("miraj", "the night journey of Isra and Miraj and the gift of salah",
                ["isra and miraj", "miraj"], ["معراج", "shab e miraj"])
    if m == 8 and d >= 20:
        return ("pre_ramadan", "preparing the heart for Ramadan",
                ["preparing for ramadan", "ramadan is coming"], ["رمضان کی تیاری", "ramzan ki tayari"])
    if now.weekday() == 4:  # Jumma
        return ("jumma", "the blessings of Friday (Jumma): Surah Kahf, durood and dua",
                ["jumma mubarak", "friday in islam"], ["جمعہ", "jumma mubarak"])
    return None


if __name__ == "__main__":
    print("occasion:", islamic_occasion())
    print("en:", suggestions(["patience in islam", "sabr"], "en", "US"))
    print("ur:", suggestions(["صبر", "sabr"], "ur", "PK"))
