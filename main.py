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
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
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

def generate_scripts_with_retry(max_retries=3, delay=15):
    # Updated to the active and supported model identifier
    model_name = 'gemini-2.0-flash'
    topic_prompt = "Think of a unique, deep, and touching Islamic motivational or spiritual topic. Give only the topic name in 3 to 6 words, nothing else."
    
    for attempt in range(1, max_retries + 1):
        try:
            topic_res = client.models.generate_content(model=model_name, contents=topic_prompt)
            chosen_topic = topic_res.text.strip()
            
            prompt_long = f"Write a deep and emotional Islamic motivational script in Roman Urdu based on this topic: {chosen_topic}. Length should be around 350 to 450 words."
            res_long = client.models.generate_content(model=model_name, contents=prompt_long)
            
            prompt_reel = f"Write a short, high-retention Islamic motivational reel script in Roman Urdu based on this topic: {chosen_topic}. Length should be around 80 to 110 words."
            res_reel = client.models.generate_content(model=model_name, contents=prompt_reel)
            
            return res_long.text, res_reel.text, chosen_topic
        except ServerError as e:
            if attempt < max_retries:
                time.sleep(delay)
            else:
                raise e
        except Exception as e:
            if attempt < max_retries:
                time.sleep(delay)
            else:
                raise e

async def text_to_speech(text, output_filename, voice_type="male"):
    voice = "ur-PK-AsadNeural" if voice_type == "male" else "ur-PK-UzmaNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_filename)

def download_pixabay_video_strictly(output_filename="bg.mp4", max_attempts=5):
    if not PIXABAY_API_KEY:
        raise Exception("Critical Error: PIXABAY_API_KEY environment variable set nahi hai!")
        
    for attempt in range(1, max_attempts + 1):
        query = random.choice(BG_QUERIES)
        url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={query}&per_page=10"
        
        try:
            response = requests.get(url, timeout=20).json()
            if "hits" in response and len(response["hits"]) > 0:
                selected_hit = random.choice(response["hits"])
                video_url = selected_hit["videos"]["medium"]["url"]
                
                vid_data = requests.get(video_url, timeout=30).content
                with open(output_filename, "wb") as f:
                    f.write(vid_data)
                
                if os.path.exists(output_filename) and os.path.getsize(output_filename) > 1024:
                    return True
        except Exception:
            pass
        
        time.sleep(5)
        
    raise Exception("Critical Error: Pixabay se video download nahi ho saki!")

def create_video_fast(audio_file, bg_video, output_video):
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
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1200)
        if result.returncode == 0:
            return True
        else:
            return False
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

def post_to_facebook(video_path, caption):
    if not FB_PAGE_ACCESS_TOKEN:
        return None
        
    url = f"https://graph-video.facebook.com/v19.0/{FB_PAGE_ID}/videos"
    
    if not os.path.exists(video_path):
        return None

    try:
        with open(video_path, 'rb') as f:
            files = {'source': f}
            data = {
                'description': caption,
                'access_token': FB_PAGE_ACCESS_TOKEN
            }
            response = requests.post(url, data=data, files=files, timeout=300)
            if response.text and response.text.strip():
                return response.json()
    except Exception:
        pass
    return None

async def main():
    long_script, reel_script, topic = generate_scripts_with_retry()
    download_pixabay_video_strictly(output_filename="bg.mp4")
    bg_file = "bg.mp4"

    # Long Video Processing
    await text_to_speech(long_script, "long_audio.mp3", voice_type="male")
    if os.path.exists("long_audio.mp3"):
        success_long = create_video_fast("long_audio.mp3", bg_file, "final_long_video.mp4")
        if success_long:
            long_caption = f"Janiye {topic} ke baray mein aik khoobsurat aur gehra paigham.\n\n#IslamicMotivation #Deeniyat #Allah #Quran #RanaAdnan"
            post_to_facebook("final_long_video.mp4", long_caption)

    # Short Reel Processing
    await text_to_speech(reel_script, "reel_audio.mp3", voice_type="female")
    if os.path.exists("reel_audio.mp3"):
        success_reel = create_video_fast("reel_audio.mp3", bg_file, "final_reel.mp4")
        if success_reel:
            reel_caption = f"Aik zaroori Islamic naseehat - {topic} 💔\n\n#Shorts #Islam #Allah #ViralReels #RanaAdnan"
            post_to_facebook("final_reel.mp4", reel_caption)

if __name__ == "__main__":
    asyncio.run(main())
