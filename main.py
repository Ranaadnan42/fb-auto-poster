import os
import asyncio
import random
import requests
import subprocess
from google import genai
from google.genai import types

# Initialize Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
model_name = 'gemini-3.6-flash'

def generate_scripts_with_retry():
    topics = [
        "When Allah Heals Your Silent Wounds",
        "The Power of Patience in Hard Times",
        "Finding Peace in the Midst of Chaos",
        "Why Every Trial is a Hidden Blessing"
    ]
    topic = random.choice(topics)
    print(f"Topic chosen: {topic}")
    
    prompt_long = f"Write a deep, engaging, and emotional script about '{topic}' for a long-form video (350-450 words). Provide only the text script to be spoken."
    prompt_reel = f"Write a short, powerful, and punchy reel script about '{topic}' (under 100 words). Provide only the text script."
    
    print("2. Generating long script...")
    res_long = client.models.generate_content(
        model=model_name,
        contents=prompt_long,
    )
    
    print("3. Generating reel script...")
    res_reel = client.models.generate_content(
        model=model_name,
        contents=prompt_reel,
    )
    
    return res_long.text, res_reel.text, topic

async def generate_audio(text, output_filename):
    import edge_tts
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_filename)

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

def post_to_facebook(video_path, title, description):
    page_access_token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    page_id = os.environ.get("FB_PAGE_ID")
    url = f"https://graph-video.facebook.com/v18.0/{page_id}/videos"
    
    with open(video_path, 'rb') as f:
        files = {'source': f}
        data = {
            'access_token': page_access_token,
            'title': title,
            'description': description
        }
        response = requests.post(url, data=data, files=files)
        return response.json()

async def main():
    print("Starting process...")
    long_script, reel_script, topic = generate_scripts_with_retry()
    
    # Audio generation
    await generate_audio(long_script, "long_audio.mp3")
    await generate_audio(reel_script, "reel_audio.mp3")
    
    # Background video download or use local dummy background
    bg_url = "https://assets.mixkit.co/videos/preview/mixkit-stars-in-the-space-background-1610-large.mp4"
    bg_file = "bg.mp4"
    if not os.path.exists(bg_file):
        r = requests.get(bg_url, stream=True)
        with open(bg_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    
    # Render Videos
    print("Rendering long video...")
    create_video("long_audio.mp3", bg_file, "final_long.mp4")
    
    print("Rendering reel video...")
    create_video("reel_audio.mp3", bg_file, "final_reel.mp4")
    
    print("Posting to Facebook...")
    post_to_facebook("final_long.mp4", topic, long_script[:300])
    print("Done successfully!")

if __name__ == "__main__":
    asyncio.run(main())
