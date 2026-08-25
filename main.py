import os
import random
import asyncio
import requests
import subprocess
from edge_tts import Communicate
import google.generativeai as genai

# ==================== CONFIGURATION ====================
PAGE_ID = "100070951321353"  # Aapki page ID
# =======================================================

# GitHub Secrets se keys uthana
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")

# Gemini configure karna
genai.configure(api_key=GEMINI_API_KEY)

def generate_dynamic_script():
    print("Gemini se SEO-optimized rozana ka naya Islamic topic aur script banwayi ja rahi hai...")
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    topics = [
        "Sabar aur mushkil waqt mein Allah ka sath",
        "Rizq mein barkat aur shukarguzari ki ahmiyat",
        "Ma baap ki khidmat aur unka maqam Islam mein",
        "Tauba aur Allah ki rehmat ka darwaza hamesha khula hai",
        "Zindagi ki haqeeqat aur akhirat ki tayari",
        "Dilon ka sukoon sirf Allah ke zikr mein hai",
        "Kisi ka dil dukhane ki saza aur achi niyat ka ajar"
    ]
    chosen_topic = random.choice(topics)
    print(f"Aaj ka SEO Topic select hua hai: {chosen_topic}")
    
    # Long script (4-5 minutes - Watch Time ke liye)
    prompt_long = f"Write a deep, emotional, and high-retention Islamic motivational script in Roman Urdu/English about '{chosen_topic}' that takes about 4 to 5 minutes to read aloud slowly. Keep it heart-touching."
    response_long = model.generate_content(prompt_long)
    long_script = response_long.text
    
    # Short script (Reel ke liye - Viral reach ke liye)
    prompt_short = f"Write a very short, highly emotional, and punchy 30-second summary script in Roman Urdu/English about '{chosen_topic}' for a Facebook Reel with a strong hook."
    response_short = model.generate_content(prompt_short)
    short_script = response_short.text
    
    return long_script, short_script, chosen_topic

async def generate_voiceover(text, output_audio):
    voices = [
        "en-US-AriaNeural",      # Female
        "en-US-GuyNeural",       # Male
        "en-GB-SoniaNeural",     # British Female
        "en-GB-RyanNeural",      # British Male
        "en-AU-NatashaNeural"    # Australian Female
    ]
    selected_voice = random.choice(voices)
    print(f"Voice select hui hai: {selected_voice} for {output_audio}")
    
    communicate = Communicate(text, selected_voice)
    await communicate.save(output_audio)

def download_pixabay_video(output_video="raw_video.mp4"):
    queries = [
        "beautiful mosque architecture cinematic",
        "night sky glowing moon stars",
        "peaceful nature landscape clouds",
        "rain falling soft lighting",
        "calming glowing lantern candle",
        "abstract spiritual peaceful background"
    ]
    selected_query = random.choice(queries)
    print(f"SEO Background theme: {selected_query}")
    
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={selected_query}&per_page=3"
    response = requests.get(url).json()
    
    if "hits" in response and len(response["hits"]) > 0:
        video_hit = random.choice(response["hits"])
        video_url = video_hit["videos"]["medium"]["url"]
        
        video_data = requests.get(video_url).content
        with open(output_video, "wb") as f:
            f.write(video_data)
        return output_video
    else:
        fallback_url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q=peaceful+nature&per_page=3"
        fallback_res = requests.get(fallback_url).json()
        if "hits" in fallback_res and len(fallback_res["hits"]) > 0:
            video_url = fallback_res["hits"][0]["videos"]["medium"]["url"]
            video_data = requests.get(video_url).content
            with open(output_video, "wb") as f:
                f.write(video_data)
            return output_video
        return None

def merge_audio_video(video_path, audio_path, final_output, is_reel=False):
    print(f"{'Reel' if is_reel else 'Long Video'} ke liye audio-video mix ki ja rahi hai...")
    if is_reel:
        command = [
            "ffmpeg", "-i", video_path, "-i", audio_path,
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-max_muxing_queue_size", "1024", final_output, "-y"
        ]
    else:
        command = [
            "ffmpeg", "-stream_loop", "-1", "-i", video_path, "-i", audio_path,
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-max_muxing_queue_size", "1024", final_output, "-y"
        ]
    subprocess.run(command, check=True)
    return final_output

def post_to_facebook(video_path, caption):
    print("Facebook Page par SEO-optimized video upload ho rahi hai...")
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/videos"
    with open(video_path, "rb") as vf:
        files = {"source": vf}
        data = {"description": caption, "access_token": FB_PAGE_TOKEN}
        res = requests.post(url, files=files, data=data).json()
        print("Facebook Response:", res)

async def main():
    # 1. SEO Script generation (Long + Short)
    long_script, short_script, topic = generate_dynamic_script()
    
    # 2. Voiceovers
    await generate_voiceover(long_script, "long_voice.mp3")
    await generate_voiceover(short_script, "short_voice.mp3")
    
    # 3. Get Background Video
    vid = download_pixabay_video("raw_video.mp4")
    
    if vid:
        # Clean topic name for hashtags (spaces remove karna)
        clean_hashtag = topic.replace(' ', '').replace('aur', '').replace('mein', '')
        
        # 4. Create & Post Long Video (SEO Optimized Caption)
        final_long_vid = merge_audio_video(vid, "long_voice.mp3", "final_long.mp4", is_reel=False)
        long_caption = f"SubhanAllah! Aaj ka khoobsurat paigham: {topic}. Zaroor sunein, dil ko sukoon milega aur apne doston ke sath share karein. ✨\n\n#IslamicReminder #Motivation #IslamicQuotes #{clean_hashtag} #Peace"
        post_to_facebook(final_long_vid, long_caption)
        
        # 5. Create & Post Short Reel (SEO Optimized Caption)
        final_reel_vid = merge_audio_video(vid, "short_voice.mp3", "final_reel.mp4", is_reel=True)
        reel_caption = f"Dil ko choo lene wali baat 💔✨ #{clean_hashtag} #IslamicReels #Shorts #Viral"
        post_to_facebook(final_reel_vid, reel_caption)

if __name__ == "__main__":
    asyncio.run(main())
