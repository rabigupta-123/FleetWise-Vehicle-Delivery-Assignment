import os
import sys
import time
import math
import http.server
import socketserver
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FRAMES_DIR = BASE_DIR / "evidence" / "video_frames"
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_PATH = Path(r"C:\Users\rabig\.gemini\antigravity\brain\433e0138-ba1f-460f-9be9-08d7598222ef\.user_uploaded\media_1793281762635_88d80d25.webm")

from playwright.sync_api import sync_playwright

class VideoHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        return str(VIDEO_PATH)

    def log_message(self, format, *args):
        pass

def run_server():
    server = socketserver.TCPServer(("127.0.0.1", 8788), VideoHandler)
    server.serve_forever()

def extract():
    print(f"Reading video from {VIDEO_PATH}")
    if not VIDEO_PATH.exists():
        print("ERROR: Video path does not exist!")
        return

    # Start HTTP server for video in background
    srv_thread = threading.Thread(target=run_server, daemon=True)
    srv_thread.start()
    time.sleep(0.5)

    video_url = "http://127.0.0.1:8788/video.webm"
    print(f"Video served at: {video_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--allow-file-access-from-files", "--disable-web-security"]
        )
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # Load video in page
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><style>body,html {{ margin:0; padding:0; background:black; overflow:hidden; }}</style></head>
        <body>
            <video id="vid" src="{video_url}" muted playsinline preload="auto" style="width:100vw; height:100vh; object-fit:contain;"></video>
        </body>
        </html>
        """
        page.set_content(html)
        
        # Wait for video metadata
        page.wait_for_function("() => { const v = document.getElementById('vid'); return v && v.readyState >= 1 && v.duration > 0; }", timeout=15000)
        
        duration = page.evaluate("() => document.getElementById('vid').duration")
        width = page.evaluate("() => document.getElementById('vid').videoWidth")
        height = page.evaluate("() => document.getElementById('vid').videoHeight")
        print(f"Video duration: {duration:.2f}s, resolution: {width}x{height}")

        # Extract 1 frame per second
        total_seconds = math.ceil(duration)
        extracted = []
        for s in range(0, total_seconds + 1):
            target_t = min(float(s), duration)
            page.evaluate(f"""() => new Promise((resolve) => {{
                const v = document.getElementById('vid');
                const onSeeked = () => {{
                    v.removeEventListener('seeked', onSeeked);
                    resolve();
                }};
                v.addEventListener('seeked', onSeeked);
                v.currentTime = {target_t};
            }})""")
            time.sleep(0.2)
            frame_name = f"frame_{s:03d}s.png"
            frame_path = FRAMES_DIR / frame_name
            page.locator("#vid").screenshot(path=str(frame_path))
            extracted.append((s, frame_name, target_t))
            print(f"Extracted {frame_name} at {target_t:.2f}s")

        browser.close()
        print(f"Finished extracting {len(extracted)} frames to {FRAMES_DIR}")

if __name__ == "__main__":
    extract()
