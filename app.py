from flask import Flask, render_template, jsonify, request
import os
import threading
from music_gen import MusicGenerator
from image_gen import ImageGenerator
from video_engine import VideoEngine
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Örnek veriler
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

# Task takipçisi
current_tasks = []

@app.route('/')
def index():
    return render_template('index.html', channels=channels, stats=stats, tasks=current_tasks)

def run_automation_flow(genre):
    """Arka planda çalışan otomasyon süreci"""
    task = {"id": len(current_tasks)+1, "name": f"{genre} Video Forge", "status": "Processing"}
    current_tasks.append(task)
    
    print(f"BAŞLATILDI: {genre} için tam otomasyon döngüsü.")
    # 1. Müzik Üret (Simülasyon veya Gerçek)
    # 2. Resim Üret
    # 3. Video Birleştir
    # 4. YouTube'a Yükle (Gelecek aşama)
    
    # Task tamamlandı - Simülasyon olduğu için şimdilik sadece bekleme
    import time
    time.sleep(5)
    task["status"] = "Success"

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

if __name__ == '__main__':
    print("\n--- YT-AUTOMATION BETA BAŞLATILIYOR ---")
    print("Local adresi: http://127.0.0.1:5000")
    print("---------------------------------------\n")
    app.run(debug=True, port=5000)
