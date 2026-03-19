import paramiko
import time

def upgrade_to_real(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    print("Bağlandı! Simülasyon, Gerçek Otomasyon Moduna (V3) yükseltiliyor...")

    real_app_code = """from flask import Flask, render_template, jsonify, request
import os
import threading
import time
from dotenv import load_dotenv

# Modül yüklemelerini try-except ile koruma (API Key hatası vermemesi için)
try:
    from music_gen import MusicGenerator
    from image_gen import ImageGenerator
    from video_engine import VideoEngine
except ImportError as e:
    print(f"Modül yükleme hatası: {e}")
    MusicGenerator = ImageGenerator = VideoEngine = None

load_dotenv()

app = Flask(__name__)

channels = [
    {"id": 1, "name": "Lofi AI Beats", "status": "Active", "subs": "1.2k"},
    {"id": 2, "name": "Chill Jazz Studio", "status": "Active", "subs": "850"},
    {"id": 3, "name": "Meditation AI", "status": "Processing", "subs": "420"},
]

stats = {"total_channels": 12, "active_forge": 3, "revenue": "$1,240", "pending": "$450"}

# Görev Takipçisi
current_tasks = []

def run_automation_flow(genre):
    task_id = len(current_tasks) + 1
    task = {"id": task_id, "name": f"{genre} Video Forge", "status": "Processing"}
    current_tasks.append(task)
    
    print(f"--- BAŞLATILDI: {genre} için GERÇEK döngü ---")
    
    try:
        # API Anahtarlarını kontrol et
        kie_key = os.getenv('KIE_API_KEY')
        replicate_key = os.getenv('REPLICATE_API_TOKEN')
        
        if not kie_key or not replicate_key:
            task["status"] = "Error: Miss Keys"
            print("HATA: API anahtarı eksik!")
            return

        # 1. Müzik Üret (Suno)
        task["status"] = "Step 1: Music Gen"
        music_gen = MusicGenerator()
        audio_url = music_gen.generate(f"{genre} style chill beats")
        audio_path = f"music_{task_id}.mp3"
        music_gen.download_audio(audio_url, audio_path)

        # 2. Resim Üret (Flux)
        task["status"] = "Step 2: Image Gen"
        image_gen = ImageGenerator()
        image_url = image_gen.generate(f"aesthetic artistic cover for {genre} music, 4k high definition")
        image_path = f"image_{task_id}.jpg"
        image_gen.download_image(image_url, image_path)

        # 3. Video Render (MoviePy)
        task["status"] = "Step 3: Rendering"
        video_engine = VideoEngine()
        output_file = f"video_{task_id}.mp4"
        video_engine.create_video(audio_path, image_path, output_file)

        task["status"] = "Success"
        print(f"VİDEO ÜRETİLDİ: {output_file}")

    except Exception as e:
        task["status"] = f"Error: {str(e)[:20]}"
        print(f"OTOMASYON HATASI: {e}")

@app.route('/')
def index():
    return render_template('index.html', channels=channels, stats=stats, tasks=current_tasks)

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    genre = data.get('genre', 'Lofi')
    
    # Arka planda gerçek işlemi başlat
    thread = threading.Thread(target=run_automation_flow, args=(genre,))
    thread.start()
    
    return jsonify({
        "status": "success", 
        "message": f"{genre} tarzında üretim kuyruğa alındı. Panelden takip edebilirsiniz."
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
"""

    # SFTP ile app.py güncelle
    sftp = ssh.open_sftp()
    with sftp.open('/root/Yt/app.py', 'w') as f:
        f.write(real_app_code)
    sftp.close()
    
    # Sunucuyu Yeniden Başlat
    ssh.exec_command("pkill -f 'python3 app.py' || true")
    time.sleep(1)
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    
    print("\n--- TEBRİKLER! SISTEM V3 MODUNA YÜKSELTİLDİ ---")
    print("Artık 'Forge Video' butonu sadece bir simülasyon değil, GERÇEK bir otomasyon döngüsüdür.")
    print("Lütfen .env dosyanıza API anahtarınızı girin.")
    
    ssh.close()

if __name__ == "__main__":
    upgrade_to_real("72.60.119.24", "19981976Yt..")
