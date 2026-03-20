import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Kie.ai Suno API Ayarları
KIE_API_KEY = os.getenv("KIE_API_KEY")
BASE_URL = "https://api.kie.ai/api/v1"

class MusicGenerator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate_music(self, prompt, model="V3_5", instrumental=True):
        """
        Suno API üzerinden müzik üretimini başlatır.
        """
        url = f"{BASE_URL}/suno/generate"
        payload = {
            "prompt": prompt,
            "model": model,
            "instrumental": instrumental,
            "customMode": False
        }

        response = requests.post(url, json=payload, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            # API yanıtı { "code": 200, "data": { "taskId": "..." } } şeklinde olabilir
            task_id = (data.get('data') or {}).get('taskId') or data.get('taskId')
            print(f"Müzik üretimi başlatıldı. Task ID: {task_id}")
            return task_id
        else:
            print(f"Hata: {response.status_code} - {response.text}")
            return None

    def check_status(self, task_id):
        """
        Üretilen müziğin durumunu kontrol eder.
        """
        url = f"{BASE_URL}/task/{task_id}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        return None

    def wait_and_download(self, task_id, output_name="output.mp3", max_retries=60):
        """
        Müzik bitene kadar bekler ve dosyayı indirir.
        max_retries: en fazla 60 deneme (10 dakika).
        """
        print("Müzik hazırlanıyor, bekleniyor...")
        retries = 0
        while retries < max_retries:
            retries += 1
            try:
                raw = self.check_status(task_id)
            except Exception as e:
                print(f"Status check error: {e}")
                time.sleep(10)
                continue

            if not raw:
                print("Status data boş, tekrar deneniyor...")
                time.sleep(10)
                continue

            # API yanıtı düz veya { "data": {...} } şeklinde olabilir
            status_data = raw.get("data", raw)
            status = status_data.get("status")

            # Numerik (2=success, 1=failed) veya string ("SUCCESS"/"FAILED") kontrol
            is_success = status == 2 or str(status).upper() in ("SUCCESS", "COMPLETE", "COMPLETED")
            is_failed  = status == 1 or str(status).upper() in ("FAILED", "ERROR")

            if is_success:
                # Şarkı listesinden ilk audioUrl'yi al
                songs = status_data.get("songs") or status_data.get("data") or []
                audio_url = None
                if isinstance(songs, list) and songs:
                    audio_url = songs[0].get("audioUrl") or songs[0].get("audio_url")
                # Düz anahtardan da dene
                audio_url = audio_url or status_data.get("audioUrl") or status_data.get("audio_url")
                if audio_url:
                    print(f"Müzik hazır! İndiriliyor: {audio_url}")
                    self.download_file(audio_url, output_name)
                else:
                    print("HATA: audioUrl bulunamadı!")
                return
            elif is_failed:
                print("Müzik üretimi başarısız oldu.")
                return

            print(f"  Durum: {status} ({retries}/{max_retries})")
            time.sleep(10)

        print("HATA: Zaman aşımı - müzik üretimi tamamlanamadı.")

    def download_file(self, url, filename):
        r = requests.get(url)
        with open(filename, 'wb') as f:
            f.write(r.content)
        print(f"Dosya kaydedildi: {filename}")

if __name__ == "__main__":
    # Test Kullanımı
    if not KIE_API_KEY:
        print("Lütfen .env dosyasına KIE_API_KEY ekleyin.")
    else:
        gen = MusicGenerator(KIE_API_KEY)
        # prompt = "Lofi hip hop for studying, chill vibes, no vocals"
        # task_id = gen.generate_music(prompt)
        # if task_id:
        #     gen.wait_and_download(task_id, "test_music.mp3")
        print("Sistem hazır. Test etmek için prompt girin.")
