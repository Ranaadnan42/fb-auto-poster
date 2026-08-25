import os
import random
import asyncio
import requests
import subprocess
from google import genai
import edge_tts

# Initialize Gemini client
client = genai.Client()

# API Keys (GitHub Secrets se uthayengi)
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")

# Aapki Facebook Page ID seedha yahan set hai
FB_PAGE_ID = "100070951321353"

# Rozana mukhtalif background videos ke liye queries ki wide list
BG_QUERIES = [
    "dark aesthetic nature mosque",
    "peaceful islamic nature background",
    "quran recitation aesthetic video",
    "makkah madinah aesthetic background",
    "deep sky stars aesthetic dark",
    "islamic architecture minaret drone",
    "rain on mosque window aesthetic",
    "desert night stars peaceful"
]

def generate_scripts():
    print("Gemini se la-mehdood categories mein se naya unique topic aur scripts banwai ja rahi hain...")
    
    # Gemini khud aik naya aur unique Islamic topic generate karega
    topic_prompt = "Think of a unique, deep, and touching Islamic motivational or spiritual topic (e.g., related to patience, rizq, parent's respect, repentance, akhirat, heart peace, trials, faith, etc.). Give only the topic name in 3 to 6 words, nothing else."
    topic_res = client.models.generate_content(model='gemini-3.6-flash', contents=topic_prompt)
    chosen_topic = topic_res.text.strip()
    print(f"Aaj ka naya auto-generated Unique Topic: {chosen_topic}")
    
    # Long Video Script (3-5 mins)
    prompt_long = f"Write a detailed, deep, and emotional Islamic motivational script in Roman Urdu based on this unique topic: {chosen_topic}. Length should be around 500-700 words with strong SEO keywords and engaging storytelling."
    res_long = client.models.generate_content(model='gemini-3.6-flash', contents=prompt_long)
    
    # Short Reel Script (30-45 secs)
    prompt_reel = f"Write a short, high-retention Islamic motivational reel script in Roman Urdu based on this unique topic: {chosen_topic}. Length should be around 100-130 words with a very powerful hook in the first 3 seconds."
    res_reel = client.models.generate_content(model='gemini-3.6-flash', contents=prompt_reel)
    
    return res_long.text, res_reel.text, chosen_topic

async def text_to_speech(text, output_filename, voice_type="male"):
    # Awaz change karne ke liye male aur female voices ka intikhab
    voice = "ur-PK-AsadNeural" if voice_type == "male" else "ur-PK-UzmaNeural"
    print(f"Edge-TTS se audio generate ho rahi hai ({voice}): {output_filename}")
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_filename)

def download_pixabay_video(output_filename="bg.mp4"):
    query = random.choice(BG_QUERIES)
    print(f"Pixabay se background video download ki ja rahi hai (Query: {query})...")
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={query}&per_page=5"
    
    try:
        response = requests.get(url).json()
        if "hits" in response and len(response["hits"]) > 0:
            selected_hit = random.choice(response["hits"])
            video_url = selected_hit["videos"]["medium"]["url"]
            vid_data = requests.get(video_url).content
            with open(output_filename, "wb") as f:
                f.write(vid_data)
            print("Background video successfully download ho gayi.")
            return True
    except Exception as e:
        print(f"Pixabay download error: {e}")
    
    print("Pixabay video nahi mili, fallback use hoga.")
    return False

def create_video(audio_file, bg_video, output_video):
    print(f"FFmpeg ke zariye background video aur audio ko merge karke professional video banayi ja rahi hai: {output_video}")
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", bg_video,
        "-i", audio_file,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        "-pix_fmt", "yuv420p",
        output_video
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print("Professional video merging mukammal ho gayi!")
    else:
        print("FFmpeg error:", result.stderr.decode('utf-8'))

def post_to_facebook(video_path, caption):
    print("Facebook Page 'Islamic Motivational Videos' par SEO hashtags ke sath video auto-upload ki ja rahi hai...")
    url = f"https://graph-video.facebook.com/v19.0/{FB_PAGE_ID}/videos"
    
    if not os.path.exists(video_path):
        print("Error: Video file exist nahi karti!")
        return
        
    with open(video_path, 'rb') as f:
        files = {'source': f}
        data = {
            'description': caption,
            'access_token': FB_PAGE_ACCESS_TOKEN
        }
        response = requests.post(url, data=data, files=files).json()
        print("Facebook API Response:", response)
        return response

async def main():
    # 1. AI se naya unique topic aur dono scripts generate karein
    long_script, reel_script, topic = generate_scripts()
    
    # 2. Pixabay se mukhtalif background video layein
    has_bg = download_pixabay_video(output_filename="bg.mp4")
    bg_file = "bg.mp4" if has_bg else None

    # --- LONG VIDEO PIPELINE (Male Voice, 3-5 Mins) ---
    print("\n--- Processing Long Video ---")
    await text_to_speech(long_script, "long_audio.mp3", voice_type="male")
    if bg_file and os.path.exists("long_audio.mp3"):
        create_video("long_audio.mp3", bg_file, "final_long_video.mp4")
        long_caption = f"Janiye {topic} ke baray mein aik khoobsurat aur gehra paigham.\n\n#IslamicMotivation #Deeniyat #Allah #Quran #IslamicReminders #RanaAdnan"
        post_to_facebook("final_long_video.mp4", long_caption)

    # --- SHORT REEL PIPELINE (Female Voice, 30-45 Secs) ---
    print("\n--- Processing Short Reel ---")
    await text_to_speech(reel_script, "reel_audio.mp3", voice_type="female")
    if bg_file and os.path.exists("reel_audio.mp3"):
        create_video("reel_audio.mp3", bg_file, "final_reel.mp4")
        reel_caption = f"Aik zaroori Islamic naseehat - {topic} 💔\n\n#Shorts #Islam #Allah #Muslim #ViralReels"
        post_to_facebook("final_reel.mp4", reel_caption)

if __name__ == "__main__":
    asyncio.run(main())
