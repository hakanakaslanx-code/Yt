from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, session
import os
import threading
import time
import traceback
from dotenv import load_dotenv, set_key

load_dotenv()

# ── Safe module imports ───────────────────────────────
HAS_MODULES = False
try:
    from music_gen import MusicGenerator
    from image_gen import ImageGenerator
    from video_engine import VideoEngine
    from yt_auth import get_auth_url, exchange_code, get_channel_info, is_connected
    from uploader import upload_video, generate_seo_metadata
    from streamer import start_stream, stop_stream, get_status as stream_status, is_ffmpeg_installed
    HAS_MODULES = True
except ImportError as e:
    print(f"[WARN] Module missing: {e}")

# Fallbacks if modules fail to import
if not HAS_MODULES:
    def is_connected(): return False
    def get_channel_info(): return None, "Modules not loaded"
    def stream_status(): return {"active": False, "key": None, "started": None, "video": None}
    def is_ffmpeg_installed(): return False
    def start_stream(*a, **kw): return False, "Modules not loaded"
    def stop_stream(*a, **kw): return False, "Modules not loaded"
    def generate_seo_metadata(g, s): return f"{g} Mix", "AI Generated", ["ai"]
    def upload_video(*a, **kw): return None

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', os.urandom(24))

# ── Data ──────────────────────────────────────────────
ENV_FILE = '/root/Yt/.env'
VIDEOS_DIR = '/root/Yt/outputs'
os.makedirs(VIDEOS_DIR, exist_ok=True)

stats = {"total_videos": 128, "credits_used": "$14.50", "active_streams": 0}
channels_demo = [
    {"id": 1, "name": "Lofi Chill Radio", "status": "Streaming", "subs": "1,240"},
    {"id": 2, "name": "Deep House Beats",  "status": "Offline",   "subs": "850"},
    {"id": 3, "name": "Meditation AI",     "status": "Processing","subs": "420"},
]
current_tasks = []

# ── Helpers ───────────────────────────────────────────
def get_file_list(ext):
    try:
        files = [f for f in os.listdir(VIDEOS_DIR) if f.endswith(ext)]
        return sorted(files, reverse=True)
    except Exception:
        return []

def file_info(filename):
    path = os.path.join(VIDEOS_DIR, filename)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    if size > 1024 * 1024:
        return {"name": filename, "size": f"{size // (1024*1024)} MB"}
    return {"name": filename, "size": f"{size // 1024} KB"}

def safe_get_yt_channel():
    """Safely get YouTube channel info, returns None on any error."""
    try:
        if is_connected():
            info, err = get_channel_info()
            if info and not err:
                return info
    except Exception as e:
        print(f"[WARN] YouTube channel info error: {e}")
    return None

# ── Automation Loop ────────────────────────────────────
def run_automation_flow(genre, style='Cinematic', lyrics_enabled=True, auto_upload=False):
    task_id = len(current_tasks) + 1
    task = {"id": task_id, "name": f"{genre} Video Forge", "status": "Initializing...", "file": None, "yt_url": None}
    current_tasks.append(task)
    try:
        if not HAS_MODULES:
            task["status"] = "Error: Server modules not loaded"
            return

        kie_key = os.getenv('KIE_API_KEY')
        replicate_key = os.getenv('REPLICATE_API_TOKEN')
        if not kie_key or not replicate_key:
            task["status"] = "Error: API Keys Missing — go to Settings"
            return

        # 1) Music
        task["status"] = "🎵 Generating Music..."
        mg = MusicGenerator(kie_key)
        mid = mg.generate_music(f"{genre} {style} chill instrumental beats")
        if not mid:
            task["status"] = "Error: Music generation failed"
            return
        audio = os.path.join(VIDEOS_DIR, f"music_{task_id}.mp3")
        mg.wait_and_download(mid, audio)
        if not os.path.exists(audio):
            task["status"] = "Error: Audio file not downloaded"
            return

        # 2) Image
        task["status"] = f"🎨 Generating {style} Art..."
        ig = ImageGenerator(replicate_key)
        img = os.path.join(VIDEOS_DIR, f"image_{task_id}.jpg")
        result = ig.generate_image(f"artwork for {genre} music video", img, style=style)
        if not result or not os.path.exists(img):
            task["status"] = "Error: Image generation failed"
            return

        # 3) Video
        task["status"] = "🎬 Rendering Video..."
        ve = VideoEngine()
        out_file = f"video_{task_id}.mp4"
        out_path = os.path.join(VIDEOS_DIR, out_file)
        ve.create_video(audio, img, f"{genre} {style} | Allone AI" if lyrics_enabled else None, out_path)
        if not os.path.exists(out_path):
            task["status"] = "Error: Video render failed"
            return
        task["file"] = out_file
        stats["total_videos"] += 1

        # 4) Upload (optional)
        if auto_upload and is_connected():
            task["status"] = "▲ Uploading to YouTube..."
            title, desc, tags = generate_seo_metadata(genre, style)
            vid_id = upload_video(out_path, title, desc, tags, privacy='private')
            if vid_id:
                task["yt_url"] = f"https://youtube.com/watch?v={vid_id}"
                task["status"] = "YouTube: Uploaded ✅"
            else:
                task["status"] = "Render OK ✅, Upload Failed"
        else:
            task["status"] = "Success ✅"
    except Exception as e:
        task["status"] = f"Error: {str(e)[:50]}"
        traceback.print_exc()

# ── Pages ─────────────────────────────────────────────
@app.route('/')
def index():
    yt_ch = safe_get_yt_channel()
    return render_template('index.html', active='dashboard',
                           channels=channels_demo, stats=stats,
                           tasks=current_tasks, yt_connected=is_connected(), yt_channel=yt_ch)

@app.route('/channels')
def channels():
    yt_ch = safe_get_yt_channel()
    return render_template('channels.html', active='channels',
                           channels=channels_demo,
                           yt_connected=is_connected(), yt_channel=yt_ch)

@app.route('/library')
def library():
    tracks = [file_info(f) for f in get_file_list('.mp3')]
    return render_template('library.html', active='library',
                           tracks=tracks, yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

@app.route('/tasks')
def tasks_page():
    return render_template('tasks.html', active='tasks',
                           tasks=current_tasks, yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

@app.route('/stream')
def stream_page():
    prefill = request.args.get('video', '')
    videos = get_file_list('.mp4')
    return render_template('stream.html', active='stream',
                           videos=videos, prefill=prefill,
                           stream_status=stream_status(), ffmpeg_ok=is_ffmpeg_installed(),
                           yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    saved = False
    if request.method == 'POST':
        kie_key = request.form.get('kie_key', '').strip()
        rep_key = request.form.get('replicate_key', '').strip()
        if kie_key:
            os.environ['KIE_API_KEY'] = kie_key
            try:
                set_key(ENV_FILE, 'KIE_API_KEY', kie_key)
            except Exception:
                pass
        if rep_key:
            os.environ['REPLICATE_API_TOKEN'] = rep_key
            try:
                set_key(ENV_FILE, 'REPLICATE_API_TOKEN', rep_key)
            except Exception:
                pass
        saved = True
    return render_template('settings.html', active='settings', saved=saved,
                           kie_key=os.getenv('KIE_API_KEY', ''),
                           replicate_key=os.getenv('REPLICATE_API_TOKEN', ''),
                           yt_connected=is_connected(), yt_channel=safe_get_yt_channel())

# ── API ───────────────────────────────────────────────
@app.route('/api/generate', methods=['POST'])
def api_generate():
    d = request.json or {}
    genre = d.get('genre', '').strip()
    if not genre:
        return jsonify({"status": "error", "message": "Genre/vibe is required"}), 400
    t = threading.Thread(target=run_automation_flow,
                         args=(genre, d.get('style', 'Cinematic'),
                               d.get('lyrics', True), d.get('auto_upload', False)))
    t.daemon = True
    t.start()
    return jsonify({"status": "success", "message": f"'{genre}' production started!"})

@app.route('/api/status')
def api_status():
    return jsonify({"tasks": current_tasks[-10:], "stats": stats, "yt_connected": is_connected()})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    d = request.json or {}
    filename = d.get('file')
    if not filename:
        return jsonify({"error": "No file specified"}), 400
    if not is_connected():
        return jsonify({"error": "YouTube account not connected"}), 401
    path = os.path.join(VIDEOS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "File not found on server"}), 404
    title, desc, tags = generate_seo_metadata("AI Music", "Cinematic")
    vid_id = upload_video(path, title, desc, tags, privacy='private')
    if vid_id:
        for t in current_tasks:
            if t.get('file') == filename:
                t['yt_url'] = f"https://youtube.com/watch?v={vid_id}"
                t['status'] = "YouTube: Uploaded ✅"
        return jsonify({"message": "✅ Uploaded!", "url": f"https://youtube.com/watch?v={vid_id}"})
    return jsonify({"error": "Upload failed"}), 500

@app.route('/api/stream/start', methods=['POST'])
def api_stream_start():
    d = request.json or {}
    stream_key = d.get('stream_key', '').strip()
    video = d.get('video', '').strip()
    if not stream_key or not video:
        return jsonify({"error": "Stream key and video are required"}), 400
    video_path = os.path.join(VIDEOS_DIR, video)
    if not os.path.exists(video_path):
        return jsonify({"error": "Video file not found"}), 404
    ok, msg = start_stream(stream_key, video_path)
    if ok:
        stats["active_streams"] = 1
    return jsonify({"message": msg, "ok": ok})

@app.route('/api/stream/stop', methods=['POST'])
def api_stream_stop():
    ok, msg = stop_stream()
    if ok:
        stats["active_streams"] = 0
    return jsonify({"message": msg, "ok": ok})

@app.route('/api/stream/status')
def api_stream_status():
    return jsonify(stream_status())

# ── YouTube Auth ──────────────────────────────────────
@app.route('/login/youtube')
def login_youtube():
    if not os.path.exists('/root/Yt/client_secrets.json'):
        return jsonify({"error": "client_secrets.json not found. Upload to VPS first."}), 400
    try:
        auth_url, state, _ = get_auth_url()
        session['yt_state'] = state
        return redirect(auth_url)
    except Exception as e:
        return jsonify({"error": f"OAuth setup failed: {str(e)}"}), 500

@app.route('/callback/youtube')
def callback_youtube():
    code = request.args.get('code')
    state = request.args.get('state')
    if not code:
        return "Error: No auth code received", 400
    try:
        exchange_code(code, state)
    except Exception as e:
        return f"Error during token exchange: {e}", 500
    return redirect('/')

@app.route('/logout/youtube')
def logout_youtube():
    try:
        if os.path.exists('/root/Yt/token.pickle'):
            os.remove('/root/Yt/token.pickle')
    except Exception:
        pass
    return redirect('/')

# ── Files ─────────────────────────────────────────────
@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(VIDEOS_DIR, filename, as_attachment=True)

@app.route('/outputs/<filename>')
def serve_output(filename):
    return send_from_directory(VIDEOS_DIR, filename)

# ── Error Handlers ────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template('index.html', active='dashboard',
                           channels=channels_demo, stats=stats,
                           tasks=current_tasks, yt_connected=is_connected(),
                           yt_channel=safe_get_yt_channel()), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "details": str(e)}), 500

if __name__ == '__main__':
    print("\n⚡ MASTER AUTO V12 — ALLONE AI")
    print(f"  Modules: {'✅ All loaded' if HAS_MODULES else '❌ Some missing'}")
    print(f"  KIE_API_KEY: {'✅ Set' if os.getenv('KIE_API_KEY') else '❌ Missing'}")
    print(f"  REPLICATE_API_TOKEN: {'✅ Set' if os.getenv('REPLICATE_API_TOKEN') else '❌ Missing'}")
    print(f"  YouTube: {'✅ Connected' if is_connected() else '❌ Not connected'}")
    print(f"  FFmpeg: {'✅ Installed' if is_ffmpeg_installed() else '❌ Not found'}")
    print("  Starting on port 5000...\n")
    app.run(host='0.0.0.0', port=5000)
