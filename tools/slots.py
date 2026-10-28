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
    # Hansi Ka Adda
    dict(file="funny.yml", crons=["8 2 * * *"], post="08:33", lead=90),
    dict(file="funny.yml", crons=["8 6 * * *"], post="12:33", lead=90),
    dict(file="funny.yml", crons=["38 8 * * *"], post="15:33", lead=120),
    dict(file="funny.yml", crons=["8 11 * * *"], post="17:33", lead=90),
    # Pics
    dict(file="photos.yml", crons=["17 0 * * *"], post="06:47", lead=60),
    dict(file="photos.yml", crons=["17 7 * * *"], post="13:47", lead=60),
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
]

WINDOW_H = 9          # ek post ke saare runs isi ghante ki khirki mein hote hain


def find(file, cron):
    for s in SLOTS:
        if s["file"] == file and cron in s["crons"]:
            return s
    return None
