"""News Act / Sports Hubs ki About aur Description (SEO) - sahi spelling aur keywords ke saath."""
import os
import requests

G = "https://graph.facebook.com/v23.0"
TEXT = {
    "news": ("NEWS", {
        "about": "Daily world news in Urdu & English: Pakistan, Middle East, Asia, Europe, America, business and "
                 "tech. Breaking news, reels and video bulletins every day. اردو اور انگریزی میں عالمی خبریں",
        "description": "News Act brings you trusted world news every day in Urdu and English - Pakistan, Gulf "
                       "(Saudi Arabia, UAE), Middle East, Asia, Europe, America, Africa, business, economy and "
                       "technology. Breaking news, short news reels and full video bulletins with sources (BBC, "
                       "Reuters, Al Jazeera, Dawn). Follow News Act for daily updates. "
                       "نیوز ایکٹ - روزانہ پاکستان اور دنیا بھر کی تازہ خبریں اردو میں۔",
    }),
    "sports": ("SPORTS", {
        "about": "Daily sports news in Urdu & English: cricket, football, tennis, boxing, F1, WWE and more. Match "
                 "recaps, reels and highlights every day. اردو اور انگریزی میں کھیلوں کی خبریں",
        "description": "Sports Hubs covers every sport around the world every day in Urdu and English - cricket "
                       "(Pakistan, PSL, ICC), football (Premier League, La Liga, Champions League, World Cup), "
                       "tennis, boxing, UFC/MMA, Formula 1, WWE, hockey, kabaddi and the Olympics. Match recaps, "
                       "breaking sports news, reels and video bulletins. Follow Sports Hubs! "
                       "سپورٹس ہبز - کرکٹ، فٹبال اور ہر کھیل کی تازہ خبریں اردو میں۔",
    }),
}
for key, (env, fields) in TEXT.items():
    pid, tok = os.environ.get(f"{env}_PAGE_ID"), os.environ.get(f"{env}_PAGE_TOKEN")
    if not pid or not tok:
        print(key, "secret missing")
        continue
    for f, v in fields.items():
        r = requests.post(f"{G}/{pid}", data={f: v, "access_token": tok}, timeout=60)
        print(key, f, r.status_code, r.text[:300])
