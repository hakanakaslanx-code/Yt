from flask import Flask, render_template, jsonify, request, send_from_directory
import os
import threading
import time
from dotenv import load_dotenv

# Modüller - Pro Versiyon
from music_gen import MusicGenerator
from image_gen import ImageGenerator
from video_engine import VideoEngine

load_dotenv()

app = Flask(__name__)

# Master Veriler (Geri Getirilen)
stats = {
    "total_videos": 128,
    "credits_used": "$14.50",
    "active_streams": 3
}

channels = [
    {"id": 1, "name": "Lofi Chill Radio", "status": "Streaming", "subs": "1,240"},
    {"id": 2, "name": "Deep House Beats", "status": "Offline", "subs": "850"},
    {"id": 3, "name": "Meditation AI", "status": "Processing", "subs": "420"},
]

# Task Takipçisi
current_tasks = []

# Çıktı Klasörü
VIDEOS_DIR = "/root/Yt/outputs"
if not os.path.exists(VIDEOS_DIR):
    os.makedirs(VIDEOS_DIR)

app.config['VIDEOS_DIR'] = VIDEOS_DIR

def run_automation_flow(genre):
    task_id = len(current_tasks) + 1
    task_name = f"{genre} Video Forge"
    task = {"id": task_id, "name": task_name, "status": "Processing"}
    current_tasks.append(task)
    
    try:
        # 1. Müzik Üret (Gerçek Suno API)
        task["status"] = "Generating Music..."
        music_gen = MusicGenerator(os.getenv("KIE_API_KEY"))
        task_id_music = music_gen.generate_music(f"{genre} style chill beats")
        audio_path = os.path.join(app.config['VIDEOS_DIR'], f"music_{task_id}.mp3")
        music_gen.wait_and_download(task_id_music, audio_path)

        # 2. Resim Üret (Flux)
        task["status"] = "Generating Image..."
        image_gen = ImageGenerator()
        image_url = image_gen.generate(f"aesthetic artistic cover for {genre} music, 4k high definition")
        image_path = os.path.join(app.config['VIDEOS_DIR'], f"image_{task_id}.jpg")
        image_gen.download_image(image_url, image_path)

        # 3. Video Birleştir (Zoom & Progress Bar Dahil)
        task["status"] = "Rendering Pro Video..."
        video_engine = VideoEngine()
        output_file = f"video_{task_id}.mp4"
        output_path = os.path.join(app.config['VIDEOS_DIR'], output_file)
        # Basit altyazı
        lyrics = f"Enjoy this {genre} vibe | Allone Master Auto"
        video_engine.create_video(audio_path, image_path, lyrics, output_path)

        task["status"] = "Success"
        print(f"--- ÜRETİM TAMAMLANDI: {output_file} ---")

    except Exception as e:
        task["status"] = "Failed"
        print(f"HATA: {e}")

@app.route('/')
def index():
    return render_template('index.html', channels=channels, stats=stats, tasks=current_tasks)

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    genre = data.get('genre', 'Lofi')
    
    # Arka planda işlemi başlat
    thread = threading.Thread(target=run_automation_flow, args=(genre,))
    thread.start()
    
    return jsonify({
        "status": "success", 
        "message": f"{genre} tarzında üretim kuyruğa alındı. Panelden takip edebilirsiniz."
    })

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['VIDEOS_DIR'], filename)

if __name__ == '__main__':
    print("\n--- MASTER AUTO V12 BAŞLATILIYOR ---")
    app.run(host='0.0.0.0', port=5000)
