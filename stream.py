import os
import json
import subprocess
import time

# ✅ Configuration
PLAY_FILE = "play.json"
RTMP_URL = os.getenv("RTMP_URL")
OVERLAY = os.path.abspath("overlay.png")
FONT_PATH = os.path.abspath("Roboto-Black.ttf")
RETRY_DELAY = 60
PREBUFFER_SECONDS = 5

# ✅ Sanity Checks
if not RTMP_URL:
    print("❌ ERROR: RTMP_URL is not set!")
    exit(1)

for path, name in [(PLAY_FILE, "Playlist JSON"), (OVERLAY, "Overlay Image"), (FONT_PATH, "Font File")]:
    if not os.path.exists(path):
        print(f"❌ ERROR: {name} '{path}' not found!")
        exit(1)

def load_movies():
    try:
        with open(PLAY_FILE, "r") as f:
            return json.load(f) or []
    except Exception as e:
        print(f"❌ Failed to load {PLAY_FILE}: {e}")
        return []

def escape_drawtext(text):
    return text.replace('\\', '\\\\\\\\').replace(':', '\\:').replace("'", "\\'")

def build_ffmpeg_command(url, title):
    text = escape_drawtext(title)

    input_options = [
        "-rw_timeout", "5000000",        # retry if no response
        "-timeout", "5000000",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-probesize", "10000000",
        "-analyzeduration", "10000000"
    ]

    if ".m3u8" in url or ".mpd" in url:
        input_options += [
            "-user_agent", "Mozilla/5.0",
            "-headers", "Referer: https://hollymoviehd.cc\r\n"
        ]

    return [
        "ffmpeg",
        "-loglevel", "warning",
        *input_options,
        "-i", url,
        "-i", OVERLAY,
        "-filter_complex",
        f"[0:v]scale=960:540:flags=bicubic,unsharp=5:5:0.8:5:5:0.0[v];"
        f"[1:v]scale=960:540[ol];"
        f"[v][ol]overlay=0:0[vo];"
        f"[vo]drawtext=fontfile='{FONT_PATH}':text='{text}':fontcolor=white:fontsize=13:x=30:y=30",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-b:v", "1300k",
        "-maxrate", "1500k",
        "-bufsize", "1500k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-f", "flv",
        RTMP_URL
    ]

def stream_movie(movie):
    title = movie.get("title", "Untitled")
    url = movie.get("url")

    if not url:
        print(f"❌ Skipping '{title}': no URL")
        return

    print(f"🎬 Streaming: {title}")
    command = build_ffmpeg_command(url, title)

    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        for line in process.stderr:
            if "403 Forbidden" in line:
                print(f"🚫 403 Forbidden! Skipping: {title}")
                process.kill()
                time.sleep(2)
                return
            if "error" in line.lower() or "failed" in line.lower():
                print("⚠️  Error:", line.strip())
            else:
                print(line.strip())
        process.wait()
    except Exception as e:
        print(f"❌ FFmpeg crashed: {e}")
        time.sleep(2)

def main():
    movies = load_movies()
    if not movies:
        print(f"📂 No entries in {PLAY_FILE}. Retrying in {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)
        return main()

    index = 0
    while True:
        stream_movie(movies[index])
        index = (index + 1) % len(movies)
        print("⏭️  Next movie in 5s...")
        time.sleep(5)

if __name__ == "__main__":
    main()
