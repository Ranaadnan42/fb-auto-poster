import os
import random
from google import genai
import edge_tts
import asyncio
import requests

client = genai.Client()

def generate_dynamic_script():
    print("Gemini se 3 se 5 minute ki long Islamic motivational script banwai ja rahi hai...")
    
    topics = [
        "Sabar aur mushkil wagt mein Allah ka sath",
        "Rizq mein barkat aur shukarguzari ki ahmiyat",
        "Ma baap ki khidmat aur unka maqam Islam mein",
        "Tauba aur Allah ki rehmat ka darwaza hamesha khula hai",
        "Zindagi ki haqeeqat aur akhirat ki tayari",
        "Dilon ka sukoon sirf Allah ke zikr mein hai",
        "Kisi ka dil dukhane ki saza aur achi niyat ka ajar"
    ]
    
    chosen_topic = random.choice(topics)
    print(f"Aaj ka long video topic select hua hai: {chosen_topic}")
    
    # Yahan prompt mein length specify kar di hai taake script 3 se 5 minute ki bane
    prompt_long = f"""Write a detailed, deep, emotional, and long Islamic motivational script in Roman Urdu/English based on this topic: {chosen_topic}. 
    Make sure the script is long enough for a 3 to 5 minute video (approximately 500 to 700 words), with proper pacing, powerful pauses, emotional storytelling, and engaging hooks for social media."""
    
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt_long
    )
    
    return response.text

if __name__ == "__main__":
    script = generate_dynamic_script()
    print("Generated Long Script (3-5 mins):")
    print(script)
