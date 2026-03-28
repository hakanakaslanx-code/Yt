import requests
import time
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()

KIE_API_KEY = os.getenv("KIE_API_KEY")
BASE_URL    = "https://api.kie.ai/api/v1"

class MusicGenerator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate_music(self, prompt, model="V5_5", instrumental=True,
                       style=None, title=None, negative_tags=None):
        """
        KIE.ai /api/v1/generate endpoint'i ile müzik üretimini başlatır.
        customMode=True ile style, title, negativeTags desteklenir.
        Dönen taskId ile durum takibi yapılır.
        """
        url = f"{BASE_URL}/generate"
        payload = {
            "prompt":       prompt[:200],   # customMode'da prompt kısa tutulur, style ayrı gönderilir
            "customMode":   True,
            "instrumental": instrumental,
            "model":        model,
            "callBackUrl":  os.getenv("CALLBACK_BASE_URL", "http://72.60.119.24:5000") + "/callback/music",
            # Kalite ve karakter ayarları
            "styleWeight":          0.7,    # stil bağlılığı (0-1)
            "weirdnessConstraint":  0.3,    # düşük = daha tutarlı/temiz ses
            "audioWeight":          0.8,    # ses kalitesi ağırlığı
        }
        if style:
            payload["style"] = style[:200]
        if title:
            payload["title"] = title[:80]
        if negative_tags:
            payload["negativeTags"] = negative_tags

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=20)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 200:
                task_id = data.get("data", {}).get("taskId")
                print(f"Muzik uretimi basladi. TaskID: {task_id}")
                return task_id
            else:
                print(f"API Hata kodu {data.get('code')}: {data.get('msg')}")
                return None
        except Exception as e:
            print(f"generate_music istisna: {e}")
            return None

    def check_status(self, task_id):
        """
        GET /api/v1/generate/record-info?taskId=... ile durum sorgular.
        """
        url = f"{BASE_URL}/generate/record-info"
        try:
            response = requests.get(url, params={"taskId": task_id},
                                    headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"check_status istisna: {e}")
            return None

    def wait_and_download(self, task_id, output_name="output.mp3", max_retries=60):
        """
        Müzik bitene kadar polling yapar (her 10 sn), hazır olunca indirir.
        Durum değerleri: PENDING → TEXT_SUCCESS → FIRST_SUCCESS → SUCCESS
        """
        print("Muzik hazirlaniyor, bekleniyor...")
        for attempt in range(1, max_retries + 1):
            raw = self.check_status(task_id)
            if not raw or raw.get("code") != 200:
                print(f"  Status okunamadi ({attempt}/{max_retries}), tekrar...")
                time.sleep(10)
                continue

            status_data = raw.get("data", {})
            status      = str(status_data.get("status", "")).upper()
            print(f"  Durum: {status} ({attempt}/{max_retries})")

            if status == "SUCCESS":
                # audio URL: data.response.sunoData[0].audioUrl
                try:
                    suno_data = status_data.get("response", {}).get("sunoData", [])
                    audio_url = None
                    if suno_data:
                        audio_url = (suno_data[0].get("audioUrl")
                                     or suno_data[0].get("audio_url")
                                     or suno_data[0].get("streamAudioUrl"))
                    if not audio_url:
                        # Yedek: düz anahtarlardan dene
                        audio_url = (status_data.get("audioUrl")
                                     or status_data.get("audio_url"))
                    if audio_url:
                        print(f"Muzik hazir! Indiriliyor...")
                        self.download_file(audio_url, output_name)
                    else:
                        print("HATA: audioUrl bulunamadi! Ham yanit:")
                        print(str(raw)[:300])
                except Exception as e:
                    print(f"Indirme hatasi: {e}")
                return

            if status in ("FAILED", "ERROR", "CREATE_FAILED"):
                print(f"Muzik uretimi basarisiz: {status}")
                return

            time.sleep(10)

        print("HATA: Zaman asimi - muzik uretilemedi.")

    def download_file(self, url, filename):
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            with open(filename, 'wb') as f:
                f.write(r.content)
            size_kb = len(r.content) // 1024
            print(f"Dosya kaydedildi: {filename} ({size_kb} KB)")
        except Exception as e:
            print(f"Dosya indirme hatasi: {e}")

    def get_audio_duration(self, path):
        """FFprobe ile ses süresini saniye olarak döner."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=15
            )
            val = result.stdout.strip()
            return float(val) if val else 0.0
        except Exception:
            return 0.0

    def generate_to_min_duration(self, prompt, output_path, min_seconds=300, model="V5_5",
                                 style=None, title=None, negative_tags=None, instrumental=True):
        """
        Minimum süreye ulaşana kadar parça üretip FFmpeg ile birleştirir.
        min_seconds: saniye (varsayılan 300 = 5 dakika)
        """
        parts = []
        total = 0.0
        attempt = 0
        base, ext = os.path.splitext(output_path)

        while total < min_seconds and attempt < 6:
            attempt += 1
            part_path = f"{base}_part{attempt}{ext}"
            print(f"[MusicGen] Parça {attempt} üretiliyor (toplam: {int(total)}s / hedef: {min_seconds}s)")
            task_id = self.generate_music(prompt, model=model, style=style,
                                          title=title, negative_tags=negative_tags,
                                          instrumental=instrumental)
            if not task_id:
                break
            self.wait_and_download(task_id, part_path)
            if os.path.exists(part_path):
                dur = self.get_audio_duration(part_path)
                if dur > 0:
                    parts.append(part_path)
                    total += dur
                    print(f"[MusicGen] Parça {attempt} hazır: {int(dur)}s → toplam: {int(total)}s")
            else:
                break

        if not parts:
            return False

        if len(parts) == 1:
            import shutil
            shutil.copy(parts[0], output_path)
        else:
            # FFmpeg concat
            list_file = f"{base}_concat_list.txt"
            try:
                with open(list_file, 'w') as f:
                    for p in parts:
                        f.write(f"file '{os.path.abspath(p)}'\n")
                # Re-encode to ensure consistent sample rate/channels across parts
                result = subprocess.run(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                     "-i", list_file,
                     "-ar", "44100", "-ac", "2", "-b:a", "192k",
                     output_path],
                    capture_output=True, timeout=300
                )
                if result.returncode != 0:
                    print(f"[MusicGen] FFmpeg concat error: {result.stderr.decode(errors='replace')}")
            finally:
                try: os.remove(list_file)
                except Exception: pass

        # Geçici parçaları sil
        for p in parts:
            try: os.remove(p)
            except Exception: pass

        final_dur = self.get_audio_duration(output_path)
        print(f"[MusicGen] Birleştirilmiş müzik: {int(final_dur)}s → {output_path}")
        return os.path.exists(output_path)


    def loop_to_duration(self, prompt, output_path, target_seconds=3600, base_parts=4,
                          model="V5_5", style=None, title=None, negative_tags=None, instrumental=True):
        """
        Birkaç parça üretir, birleştirir, ardından FFmpeg stream loop ile
        hedef süreye uzatır. Kredi tasarrufu: sadece base_parts kadar üretim.
        target_seconds: saniye (varsayılan 3600 = 1 saat)
        base_parts: kaç parça üretilsin (varsayılan 4 ≈ 12-16 dk)
        """
        base, ext = os.path.splitext(output_path)
        base_audio = f"{base}_base{ext}"

        # Adım 1: base_parts kadar parça üret ve birleştir
        parts = []
        for i in range(1, base_parts + 1):
            part_path = f"{base}_loop_part{i}{ext}"
            print(f"[MusicLoop] Parça {i}/{base_parts} üretiliyor...")
            task_id = self.generate_music(prompt, model=model, style=style,
                                          title=title, negative_tags=negative_tags,
                                          instrumental=instrumental)
            if not task_id:
                print(f"[MusicLoop] Parça {i} üretilemedi, atlanıyor.")
                continue
            self.wait_and_download(task_id, part_path)
            if os.path.exists(part_path):
                dur = self.get_audio_duration(part_path)
                if dur > 0:
                    parts.append(part_path)
                    print(f"[MusicLoop] Parça {i} hazır: {int(dur)}s")

        if not parts:
            print("[MusicLoop] Hiç parça üretilemedi!")
            return False

        # Adım 2: parçaları birleştir → base_audio
        if len(parts) == 1:
            import shutil
            shutil.copy(parts[0], base_audio)
        else:
            list_file = f"{base}_loop_list.txt"
            try:
                with open(list_file, 'w') as f:
                    for p in parts:
                        f.write(f"file '{os.path.abspath(p)}'\n")
                result = subprocess.run(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                     "-i", list_file,
                     "-ar", "44100", "-ac", "2", "-b:a", "192k",
                     base_audio],
                    capture_output=True, timeout=300
                )
                if result.returncode != 0:
                    print(f"[MusicLoop] Concat hatası: {result.stderr.decode(errors='replace')}")
            finally:
                try: os.remove(list_file)
                except Exception: pass

        # Geçici parçaları temizle
        for p in parts:
            try: os.remove(p)
            except Exception: pass

        if not os.path.exists(base_audio):
            print("[MusicLoop] Base audio oluşturulamadı!")
            return False

        base_dur = self.get_audio_duration(base_audio)
        print(f"[MusicLoop] Base audio: {int(base_dur)}s → {int(target_seconds)}s'ye loop yapılıyor...")

        # Adım 3: FFmpeg stream_loop ile hedef süreye uzat
        result = subprocess.run(
            ["ffmpeg", "-y",
             "-stream_loop", "-1",
             "-i", base_audio,
             "-t", str(target_seconds),
             "-ar", "44100", "-ac", "2", "-b:a", "192k",
             output_path],
            capture_output=True, timeout=600
        )

        try: os.remove(base_audio)
        except Exception: pass

        if result.returncode != 0:
            print(f"[MusicLoop] Loop hatası: {result.stderr.decode(errors='replace')}")
            return False

        final_dur = self.get_audio_duration(output_path)
        print(f"[MusicLoop] Tamamlandı: {int(final_dur)}s → {output_path}")
        return os.path.exists(output_path)


if __name__ == "__main__":
    if not KIE_API_KEY:
        print("KIE_API_KEY eksik!")
    else:
        gen = MusicGenerator(KIE_API_KEY)
        print("MusicGenerator hazir.")
