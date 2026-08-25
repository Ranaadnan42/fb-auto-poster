import os
import random
from google import genai
import edge_tts
import asyncio
import requests

client = genai.Client()

def generate_dynamic_script():
    print("Gemini se SEO-optimized rozana ka naya Islamic topic aur script banwai ja rahi hai...")
    
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
    print(f"Aaj ka SEO Topic select hua hai: {chosen_topic}")
    
    prompt_long = f"Write a deep, emotional, and high-retention Islamic motivational script in Roman Urdu/English based on this topic: {chosen_topic}. Make it engaging for social media with proper SEO keywords."
    
    # Naye client ke sath saheeh model format
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt_long,
    )
    
    return response.text

if __name__ == "__main__":
    script = generate_dynamic_script()
    print("Generated Script:")
    print(script)
