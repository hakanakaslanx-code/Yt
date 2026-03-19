import subprocess
import os
import signal
import threading
import time

# Aktif stream süreci
_stream_process = None
_stream_status = {"active": False, "key": None, "started": None, "video": None}

def start_stream(stream_key, video_path, loop=True):
    """
    FFmpeg ile YouTube'a RTMP canlı yayın başlatır.
    
    Args:
        stream_key: YouTube Studio'dan alınan stream anahtarı
        video_path: MP4 dosya yolu (döngüde yayınlanır)
        loop: True ise video bitmeyecek, tekrar tekrar oynatılacak
    """
    global _stream_process, _stream_status

    if _stream_process and _stream_process.poll() is None:
        return False, "Zaten aktif bir yayın var."

    if not os.path.exists(video_path):
        return False, f"Video dosyası bulunamadı: {video_path}"

    rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
    
    # FFmpeg komutu - 24/7 döngüsel yayın için
    loop_flag = ["-stream_loop", "-1"] if loop else []
    
    cmd = [
        "ffmpeg",
        "-re",                          # Gerçek zamanlı okuma
        *loop_flag,                     # Sonsuz döngü
        "-i", video_path,               # Giriş video
        "-c:v", "libx264",              # Video codec
        "-preset", "veryfast",          # Hızlı encode
        "-b:v", "2500k",                # Video bitrate
        "-maxrate", "2500k",
        "-bufsize", "5000k",
        "-pix_fmt", "yuv420p",
        "-g", "60",                     # Keyframe her 2 saniyede
        "-c:a", "aac",                  # Ses codec
        "-b:a", "128k",
        "-ar", "44100",
        "-f", "flv",                    # YouTube RTMP formatı
        rtmp_url
    ]
    
    _stream_process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )
    
    _stream_status = {
        "active": True,
        "key": stream_key[:8] + "****",  # Güvenlik için kısa göster
        "started": time.strftime("%H:%M:%S"),
        "video": os.path.basename(video_path)
    }
    
    print(f"🔴 CANLI YAYIN BAŞLADI: {rtmp_url}")
    return True, "Yayın başarıyla başlatıldı."

def stop_stream():
    """Aktif yayını durdurur."""
    global _stream_process, _stream_status
    
    if _stream_process and _stream_process.poll() is None:
        _stream_process.terminate()
        try:
            _stream_process.wait(timeout=5)
        except:
            _stream_process.kill()
        _stream_process = None
        _stream_status = {"active": False, "key": None, "started": None, "video": None}
        print("⬛ YAYIN DURDURULDU")
        return True, "Yayın durduruldu."
    
    return False, "Aktif yayın yok."

def get_status():
    """Mevcut yayın durumunu döndürür."""
    global _stream_process, _stream_status
    
    if _stream_process and _stream_process.poll() is None:
        _stream_status["active"] = True
    else:
        _stream_status["active"] = False
    
    return _stream_status

def is_ffmpeg_installed():
    """FFmpeg kurulu mu kontrol eder."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], 
                               capture_output=True, timeout=3)
        return result.returncode == 0
    except:
        return False
