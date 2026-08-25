import os
import random
import asyncio
import requests
import subprocess
import time
from google import genai
import edge_tts
from google.genai.errors import ServerError

# Initialize Gemini client
client = genai.Client()

PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_TOKEN") # Aapke secret wala naam yahan set hai
FB_PAGE_ID = "100070951321353"

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

def generate_scripts_with_retry():
    model_name = 'gemini-3.6-flash'
    topic_prompt = "Think of a unique, deep, and touching Islamic motivational or spiritual topic. Give only the topic name in 3 to 6 words, nothing else."
    
    print("1. Generating topic from Gemini...")
    topic_res = client.models.generate_content(model=model_name, contents=topic_prompt)
    chosen_topic = topic_res.text.strip()
    print(f"Topic chosen: {chosen_topic}")
    
    print("Waiting 10 seconds to avoid rate limit...")
    time.sleep(10)
    
    print("2. Generating long script (350-450 words)...")
    prompt_long = f"Write a deep and emotional Islamic motivational script in Roman Urdu based on this topic: {chosen_topic}. Length should be around 350 to 450 words."
    res_long = client.models.generate_content(model=model_name, contents=prompt_long)
    
    print("Waiting 10 seconds to avoid rate limit...")
    time.sleep(10)
    
    print("3. Generating reel script (80-110 words)...")
    prompt_reel = f"Write a short, high-retention Islamic motivational reel script in Roman Urdu based on this topic: {chosen_topic}. Length should be around 80 to 110 words."
    res_reel = client.models.generate_content(model=model_name, contents=prompt_reel)
    
    return res_long.text, res_reel.text, chosen_topic

async def text_to_speech(text, output_filename, voice_type="male"):
    voice = "ur-PK-AsadNeural" if voice_type == "male" else "ur-PK-UzmaNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_filename)

def download_pixabay_video(output_filename="bg.mp4"):
    if not PIXABAY_API_KEY:
        raise Exception("Critical Error: PIXABAY_API_KEY set nahi hai!")
        
    query = random.choice(BG_QUERIES)
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={query}&per_page=10"
    
    response = requests.get(url, timeout=20).json()
    if "hits" in response and len(response["hits"]) > 0:
        selected_hit = random.choice(response["hits"])
        video_url = selected_hit["videos"]["medium"]["url"]
        
        vid_data = requests.get(video_url, timeout=30).content
        with open(output_filename, "wb") as f:
            f.write(vid_data)
        return True
    else:
        raise Exception("Pixabay se video nahi mil saki!")

def create_video(audio_file, bg_video, output_video):
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", bg_video,
        "-i", audio_file,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-shortest",
        "-pix_fmt", "yuv420p",
        output_video
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Exception(f"FFmpeg Error: {result.stderr.decode('utf-8', errors='ignore')}")
    return True

def post_to_facebook(video_path, caption):
    if not FB_PAGE_ACCESS_TOKEN:
        raise Exception("FB_PAGE_TOKEN missing hai!")
        
    url = f"https://graph-video.facebook.com/v19.0/{FB_PAGE_ID}/videos"
    
    with open(video_path, 'rb') as f:
        files = {'source': f}
        data = {
            'description': caption,
            'access_token': FB_PAGE_ACCESS_TOKEN
        }
        response = requests.post(url, data=data, files=files, timeout=300)
        print(f"FB Response Code: {response.status_code}")
        print(f"FB Response Body: {response.text}")
        
        if response.status_code != 200:
            raise Exception(f"Facebook Upload Failed: {response.text}")
        return response.json()

async def main():
    print("Starting process...")
    long_script, reel_script, topic = generate_scripts_with_retry()
    
    print("4. Downloading background video...")
    download_pixabay_video(output_filename="bg.mp4")
    bg_file = "bg.mp4"

    print("5. Processing Long Video (Audio + Video)...")
    await text_to_speech(long_script, "long_audio.mp3", voice_type="male")
    create_video("long_audio.mp3", bg_file, "final_long_video.mp4")
    
    print("6. Posting Long Video to Facebook...")
    long_caption = f"Janiye {topic} ke baray mein aik khoobsurat aur gehra paigham.\n\n#IslamicMotivation #Deeniyat #Allah #Quran #RanaAdnan"
    post_to_facebook("final_long_video.mp4", long_caption)

    print("7. Processing Short Reel...")
    await text_to_speech(reel_script, "reel_audio.mp3", voice_type="female")
    create_video("reel_audio.mp3", bg_file, "final_reel.mp4")
    
    print("8. Posting Short Reel to Facebook...")
    reel_caption = f"Aik zaroori Islamic naseehat - {topic} 💔\n\n#Shorts #Islam #Allah #ViralReels #RanaAdnan"
    post_to_facebook("final_reel.mp4", reel_caption)
    
    print("All tasks completed and posted successfully!")

if __name__ == "__main__":
    asyncio.run(main())
