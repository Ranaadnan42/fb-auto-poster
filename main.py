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
    # Timeout ko barha kar 600 seconds (10 minutes) kar diya hai
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    if result.returncode == 0:
        print("Video merging mukammal ho gayi!")
        return True
    else:
        print("FFmpeg Error:", result.stderr.decode('utf-8'))
        return False
