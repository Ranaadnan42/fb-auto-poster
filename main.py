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
    topic_prompt = "Think of a unique, deep, and touching Islamic motivational or spiritual topic. Give only the topic name in 3 to 6 words, nothing else."
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Gemini se topic aur scripts banwane ki koshish (Attempt {attempt}/{max_retries})...")
            topic_res = client.models.generate_content(model='gemini-2.5-flash', contents=topic_prompt)
            chosen_topic = topic_res.text.strip()
            print(f"Aaj ka auto-generated Unique Topic: {chosen_topic}")
            
            prompt_long = f"Write a detailed, deep, and emotional Islamic motivational script in Roman Urdu based on this unique topic: {chosen_topic}. Length should be around 400-500 words."
            res_long = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_long)
            
            prompt_reel = f"Write a short, high-retention Islamic motivational reel script in Roman Urdu based on this unique topic: {chosen_topic}. Length should be around 100-130 words."
            res_reel = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_reel)
            
            return res_long.text, res_reel.text, chosen_topic
        except ServerError as e:
            print(f"Google Server Error (503/Overloaded): {e}")
            if attempt < max_retries:
                time.sleep(delay)
            else:
                raise e
        except Exception as e:
            print(f"Other Gemini Error: {e}")
            if attempt < max_retries:
                time.sleep(delay)
            else:
                raise e

async def text_to_speech(text, output_filename, voice_type="male"):
    voice = "ur-PK-AsadNeural" if voice_type == "male" else "ur-PK-UzmaNeural"
    print(f"Edge-TTS se audio generate ho rahi hai ({voice}): {output_filename}")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_filename)

def download_pixabay_video_strictly(output_filename="bg.mp4", max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        query = random.choice(BG_QUERIES)
        print(f"Pixabay se background video uthane ki koshish {attempt}/{max_attempts} (Query: {query})...")
        url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={query}&per_page=10"
        
        try:
            response = requests.get(url, timeout=20).json()
            if "hits" in response and len(response["hits"]) > 0:
                selected_hit = random.choice(response["hits"])
                video_url = selected_hit["videos"]["medium"]["url"]
                
                print(f"Video mil gayi, download ki ja rahi hai...")
                vid_data = requests.get(video_url, timeout=30).content
                with open(output_filename, "wb") as f:
                    f.write(vid_data)
                
                if os.path.exists(output_filename) and os.path.getsize(output_filename) > 1024:
                    print("Pixabay video successfully download ho kar save ho gayi!")
                    return True
        except Exception as e:
            print(f"Download attempt {attempt} mein masla aya: {e}")
        
        time.sleep(5)
        
    raise Exception("Critical Error: Pixabay se kisi bhi query par video download nahi ho saki!")

def create_video(audio_file, bg_video, output_video):
    print(f"FFmpeg ke zariye video aur audio merge ho rahi hai: {output_video}")
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
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    if result.returncode == 0:
        print("Video merging mukammal ho gayi!")
        return True
    else:
        print("FFmpeg Error:", result.stderr.decode('utf-8'))
        return False

def post_to_facebook(video_path, caption):
    print("Facebook Page par video upload ki ja rahi hai...")
    url = f"https://graph-video.facebook.com/v19.0/{FB_PAGE_ID}/videos"
    
    if not os.path.exists(video_path):
        print("Error: Video file exist nahi karti upload ke liye!")
        return None

    try:
        with open(video_path, 'rb') as f:
            files = {'source': f}
            data = {
                'description': caption,
                'access_token': FB_PAGE_ACCESS_TOKEN
            }
            response = requests.post(url, data=data, files=files, timeout=180)
            print(f"Facebook Status Code: {response.status_code}")
            print(f"Facebook Response: {response.text}")
            if response.text and response.text.strip():
                return response.json()
    except Exception as e:
        print(f"Facebook upload exception: {e}")
    return None

async def main():
    print("Automation script start ho gayi hai...")
    long_script, reel_script, topic = generate_scripts_with_retry()
    
    download_pixabay_video_strictly(output_filename="bg.mp4")
    bg_file = "bg.mp4"

    print("\n--- Processing Long Video ---")
    await text_to_speech(long_script, "long_audio.mp3", voice_type="male")
    if os.path.exists("long_audio.mp3"):
        success = create_video("long_audio.mp3", bg_file, "final_long_video.mp4")
        if success:
            long_caption = f"Janiye {topic} ke baray mein aik khoobsurat aur gehra paigham.\n\n#IslamicMotivation #Deeniyat #Allah #Quran #RanaAdnan"
            post_to_facebook("final_long_video.mp4", long_caption)

    print("\n--- Processing Short Reel ---")
    await text_to_speech(reel_script, "reel_audio.mp3", voice_type="female")
    if os.path.exists("reel_audio.mp3"):
        success = create_video("reel_audio.mp3", bg_file, "final_reel.mp4")
        if success:
            reel_caption = f"Aik zaroori Islamic naseehat - {topic} 💔\n\n#Shorts #Islam #Allah #ViralReels"
            post_to_facebook("final_reel.mp4", reel_caption)

    print("Tamam process mukammal ho gaya hai!")

if __name__ == "__main__":
    asyncio.run(main())
