import os
import asyncio
import random
import requests
import subprocess
from google import genai
from google.genai import types

# Initialize Gemini Client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
# 'gemini-3.6-flash' naam ka model mojood nahi tha - pehla chalne wala model use hoga
MODEL_CANDIDATES = ['gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-3.5-flash-lite']

def generate_text(prompt):
    last_err = None
    for m in MODEL_CANDIDATES:
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            if res.text and res.text.strip():
                print(f"   model used: {m}")
                return res.text.strip()
        except Exception as e:
            print(f"   {m} failed: {e}")
            last_err = e
    raise Exception(f"Gemini se script nahi bani: {last_err}")

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
    long_text = generate_text(prompt_long)
    
    print("3. Generating reel script...")
    reel_text = generate_text(prompt_reel)
    
    return long_text, reel_text, topic

async def generate_audio(text, output_filename):
    import edge_tts
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_filename)

def create_video(audio_file, bg_video, output_video, vertical=False):
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", bg_video,
        "-i", audio_file,
    ]
    if vertical:
        # Reel ke liye 9:16 (1080x1920), 30fps zaroori hai
        cmd += ["-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30"]
    cmd += [
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
    if not page_access_token or not page_id:
        raise Exception("FB_PAGE_ACCESS_TOKEN ya FB_PAGE_ID secret missing hai")
    url = f"https://graph-video.facebook.com/v23.0/{page_id}/videos"
    
    with open(video_path, 'rb') as f:
        files = {'source': f}
        data = {
            'access_token': page_access_token,
            'title': title,
            'description': description
        }
        response = requests.post(url, data=data, files=files, timeout=3600)
    result = response.json()
    if "error" in result:
        raise Exception(f"Facebook error: {result['error'].get('message', result)}")
    print(f"Facebook post id: {result.get('id')}")
    return result

def post_reel_to_facebook(video_path, description):
    page_access_token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    page_id = os.environ.get("FB_PAGE_ID")
    if not page_access_token or not page_id:
        raise Exception("FB_PAGE_ACCESS_TOKEN ya FB_PAGE_ID secret missing hai")
    base = f"https://graph.facebook.com/v23.0/{page_id}/video_reels"

    def check(r):
        j = r.json()
        if "error" in j:
            raise Exception(f"Facebook reel error: {j['error'].get('message', j)}")
        return j

    # 1) start
    vid = check(requests.post(base, data={"upload_phase": "start",
                                          "access_token": page_access_token}, timeout=60))["video_id"]
    # 2) upload
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        check(requests.post(f"https://rupload.facebook.com/video-upload/v23.0/{vid}",
                            headers={"Authorization": f"OAuth {page_access_token}",
                                     "offset": "0", "file_size": str(size)},
                            data=f, timeout=1800))
    # 3) publish
    check(requests.post(base, data={"upload_phase": "finish", "video_id": vid,
                                     "video_state": "PUBLISHED", "description": description,
                                     "access_token": page_access_token}, timeout=60))
    print(f"Facebook reel id: {vid}")
    return vid

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
        ok = False
        try:
            r = requests.get(bg_url, stream=True, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and "video" in r.headers.get("Content-Type", ""):
                with open(bg_file, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
                ok = True
            else:
                print(f"Background download fail: HTTP {r.status_code}")
        except Exception as e:
            print(f"Background download fail: {e}")
        if not ok:
            # Link band ho to khud ek simple background video bana lo
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                            "gradients=s=1080x1920:c0=0x0b1a33:c1=0x1f4d7a:speed=0.01:d=20",
                            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", bg_file],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
    # Render Videos
    print("Rendering long video...")
    create_video("long_audio.mp3", bg_file, "final_long.mp4")
    
    print("Rendering reel video...")
    create_video("reel_audio.mp3", bg_file, "final_reel.mp4", vertical=True)
    
    print("Posting to Facebook...")
    post_to_facebook("final_long.mp4", topic, long_script[:300])

    print("Posting reel to Facebook...")
    post_reel_to_facebook("final_reel.mp4", f"{topic}\n\n{reel_script[:300]}")
    print("Done successfully!")

if __name__ == "__main__":
    asyncio.run(main())
