def post_to_facebook(video_path, caption):
    print("Facebook Page 'Islamic Motivational Videos' par video upload ki ja rahi hai...")
    url = f"https://graph-video.facebook.com/v19.0/{FB_PAGE_ID}/videos"
    
    if not os.path.exists(video_path):
        print("Error: Video file exist nahi karti!")
        return None
        
    try:
        with open(video_path, 'rb') as f:
            files = {'source': f}
            data = {
                'description': caption,
                'access_token': FB_PAGE_ACCESS_TOKEN
            }
            # Timeout barha kar 120 seconds kar diya hai taake badi video upload hone mein waqt le sakay
            response = requests.post(url, data=data, files=files, timeout=120)
            print(f"Facebook Status Code: {response.status_code}")
            print(f"Facebook Response Text: {response.text}")
            
            # Check karein ke response khali toh nahi hai
            if response.text and response.text.strip():
                return response.json()
            else:
                print("Warning: Facebook ki taraf se khali response mila hai.")
                return None
                
    except Exception as e:
        print(f"Facebook upload error: {e}")
        return None
