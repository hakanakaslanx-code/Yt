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
        url = f"{BASE_URL}/generate"
        payload = {
            "prompt": prompt,
            "model": model,
            "instrumental": instrumental
        }
        
        response = requests.post(url, json=payload, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            print(f"Müzik üretimi başlatıldı. Task ID: {data.get('taskId')}")
            return data.get('taskId')
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

    def wait_and_download(self, task_id, output_name="output.mp3"):
        """
        Müzik bitene kadar bekler ve dosyayı indirir.
        """
        print("Müzik hazırlanıyor, bekleniyor...")
        while True:
            status_data = self.check_status(task_id)
            if not status_data:
                break
                
            status = status_data.get("status")
            if status == "SUCCESS":
                audio_url = status_data.get("audioUrl")
                print(f"Müzik hazır! İndiriliyor: {audio_url}")
                self.download_file(audio_url, output_name)
                break
            elif status == "FAILED":
                print("Müzik üretimi başarısız oldu.")
                break
            
            time.sleep(10) # 10 saniye bekle

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
