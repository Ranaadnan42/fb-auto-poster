"""
Har post ka waqt ek jagah (UTC). Scheduler (keeper.py) aur gate (slot_gate.py) dono yahi table use karte hain.

file   = workflow file
crons  = us post ke cron (pehla asli, baqi backup) - run ke naam mein [cron] likha hota hai
post   = post ka waqt UTC "HH:MM"
lead   = post se kitne minute pehle Scheduler bot ko chalaye (video banne ka waqt)
"""

SLOTS = [
    # Islamic page (Daily Auto Poster)
    dict(file="main.yml", crons=["37 1 * * *"], post="08:07", lead=90),
    dict(file="main.yml", crons=["17 9 * * *"], post="16:17", lead=120),
    dict(file="main.yml", crons=["37 11 * * *"], post="18:07", lead=90),
    dict(file="main.yml", crons=["17 14 * * *"], post="21:17", lead=120),
    dict(file="main.yml", crons=["7 6 * * *"], post="12:37", lead=90),     # 2nd Urdu reel (FB weekly task)
    # Hansi Ka Adda
    dict(file="funny.yml", crons=["8 2 * * *"], post="08:33", lead=90),
    dict(file="funny.yml", crons=["8 6 * * *"], post="12:33", lead=90),
    dict(file="funny.yml", crons=["38 8 * * *"], post="15:33", lead=120),
    dict(file="funny.yml", crons=["8 11 * * *"], post="17:33", lead=90),
    # Pics
    dict(file="photos.yml", crons=["17 0 * * *"], post="06:47", lead=60),
    dict(file="photos.yml", crons=["17 7 * * *"], post="13:47", lead=60),
    # FB weekly task (photo posts) - Islamic + Hansi Ka Adda par zyada pics
    dict(file="photos.yml", crons=["47 2 * * *"], post="08:47", lead=60),
    dict(file="photos.yml", crons=["47 4 * * *"], post="10:47", lead=60),
    dict(file="photos.yml", crons=["17 10 * * *"], post="16:47", lead=60),
    # Frames of Life
    dict(file="frames.yml", crons=["47 1 * * *"], post="08:17", lead=100),
    dict(file="frames.yml", crons=["47 6 * * *"], post="13:17", lead=100),
    dict(file="frames.yml", crons=["7 10 * * *"], post="17:07", lead=150),
    # Atlas Untold
    dict(file="world.yml", crons=["17 8 * * *"], post="14:47", lead=100),
    dict(file="world.yml", crons=["37 13 * * *"], post="20:37", lead=150),
    dict(file="world.yml", crons=["47 17 * * *"], post="00:17", lead=100),
    # Legends Untold
    dict(file="cinematic.yml", crons=["47 9 * * *", "17 10 * * *"], post="16:17", lead=150),
    dict(file="cinematic.yml", crons=["7 15 * * *", "37 15 * * *"], post="22:07", lead=180),
    dict(file="cinematic.yml", crons=["47 18 * * *", "17 19 * * *"], post="01:17", lead=150),
    # Web Builder (pics + reels + long, en/ur/ar) - turant post karta hai
    dict(file="webbuilder.yml", crons=["23 10 * * *"], post="10:23", lead=15),
    dict(file="webbuilder.yml", crons=["33 11 * * *"], post="11:33", lead=15),
    dict(file="webbuilder.yml", crons=["37 13 * * *"], post="13:37", lead=15),
    dict(file="webbuilder.yml", crons=["7 15 * * *"], post="15:07", lead=15),
    dict(file="webbuilder.yml", crons=["47 16 * * *"], post="16:47", lead=15),
    dict(file="webbuilder.yml", crons=["43 17 * * *"], post="17:43", lead=15),
    dict(file="webbuilder.yml", crons=["27 18 * * *"], post="18:27", lead=15),
    dict(file="webbuilder.yml", crons=["13 19 * * *"], post="19:13", lead=15),
    dict(file="webbuilder.yml", crons=["3 20 * * *"], post="20:03", lead=15),
    # News Act + Sports Hubs (pics turant, reel/long ban kar post)
    dict(file="news.yml", crons=["56 1 * * *"], post="02:11", lead=15),
    dict(file="news.yml", crons=["26 5 * * *"], post="05:41", lead=15),
    dict(file="news.yml", crons=["56 9 * * *"], post="10:11", lead=15),
    dict(file="news.yml", crons=["26 14 * * *"], post="14:41", lead=15),
    dict(file="news.yml", crons=["51 7 * * *"], post="08:21", lead=30),
    dict(file="news.yml", crons=["51 15 * * *"], post="16:21", lead=30),
    dict(file="news.yml", crons=["46 14 * * *"], post="15:31", lead=45),
    dict(file="news.yml", crons=["16 20 * * *"], post="21:01", lead=45),
    # News/Sports: 4 aur reels + har 2 ghante breaking check
    dict(file="news.yml", crons=["51 3 * * *"], post="04:21", lead=30),
    dict(file="news.yml", crons=["21 12 * * *"], post="12:51", lead=30),
    dict(file="news.yml", crons=["21 19 * * *"], post="19:51", lead=30),
    dict(file="news.yml", crons=["21 23 * * *"], post="23:51", lead=30),
    dict(file="news.yml", crons=["7 0 * * *"], post="00:17", lead=10),
    dict(file="news.yml", crons=["7 2 * * *"], post="02:17", lead=10),
    dict(file="news.yml", crons=["7 4 * * *"], post="04:17", lead=10),
    dict(file="news.yml", crons=["7 6 * * *"], post="06:17", lead=10),
    dict(file="news.yml", crons=["7 8 * * *"], post="08:17", lead=10),
    dict(file="news.yml", crons=["7 10 * * *"], post="10:17", lead=10),
    dict(file="news.yml", crons=["7 12 * * *"], post="12:17", lead=10),
    dict(file="news.yml", crons=["7 14 * * *"], post="14:17", lead=10),
    dict(file="news.yml", crons=["7 16 * * *"], post="16:17", lead=10),
    dict(file="news.yml", crons=["7 18 * * *"], post="18:17", lead=10),
    dict(file="news.yml", crons=["7 20 * * *"], post="20:17", lead=10),
    dict(file="news.yml", crons=["7 22 * * *"], post="22:17", lead=10),
    dict(file="news.yml", crons=["33 6 * * *"], post="07:03", lead=30),
    dict(file="news.yml", crons=["33 17 * * *"], post="18:03", lead=30),
    dict(file="news.yml", crons=["3 22 * * *"], post="22:33", lead=30),
    # Comment Helper search (Facebook posts dhoondta hai -> comment_hits.json; Supabase 04:15/13:15 email)
    dict(file="comment_search.yml", crons=["41 3 * * *"], post="03:41", lead=10),
    dict(file="comment_search.yml", crons=["41 12 * * *"], post="12:41", lead=10),
]

WINDOW_H = 9          # ek post ke saare runs isi ghante ki khirki mein hote hain


def find(file, cron):
    for s in SLOTS:
        if s["file"] == file and cron in s["crons"]:
            return s
    return None
