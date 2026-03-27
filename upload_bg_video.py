"""
Arka plan videosunu dogrudan SFTP ile VPS'e yukler.
Kullanim: python upload_bg_video.py "C:\Users\...\video.mp4"
"""
import sys
import os
import paramiko

VPS_IP       = "72.60.119.24"
VPS_USER     = "root"
VPS_PASSWORD = "19981976Yt.."
REMOTE_PATH  = "/tmp/yt_stream_bg.mp4"

def upload(local_path):
    if not os.path.exists(local_path):
        print(f"HATA: Dosya bulunamadi: {local_path}")
        return

    size_mb = os.path.getsize(local_path) / 1024 / 1024
    print(f"Dosya: {os.path.basename(local_path)} ({size_mb:.1f} MB)")
    print(f"VPS'e yukleniyor: {VPS_IP}:{REMOTE_PATH}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_IP, username=VPS_USER, password=VPS_PASSWORD, timeout=15)
    sftp = ssh.open_sftp()

    uploaded = [0]
    def progress(sent, total):
        pct = sent / total * 100
        bar = '#' * int(pct / 2)
        print(f"\r  [{bar:<50}] {pct:.1f}%", end='', flush=True)

    sftp.put(local_path, REMOTE_PATH, callback=progress)
    print("\nYukleme tamamlandi!")

    # ffprobe ile dogrula
    stdin, stdout, stderr = ssh.exec_command(
        f"ffprobe -v error -select_streams v:0 -show_entries stream=width "
        f"-of default=noprint_wrappers=1 {REMOTE_PATH} 2>&1 | head -3"
    )
    result = stdout.read().decode('utf-8', errors='replace').strip()
    if result:
        print(f"Video dogrulandi: {result}")
        print("\nHazir! Simdi Stream sayfasindan yayini baslatabilirsiniz.")
    else:
        print("UYARI: Video dogrulanamadi, dosya bozuk olabilir.")

    sftp.close()
    ssh.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanim: python upload_bg_video.py \"dosya_yolu.mp4\"")
        print('Ornek:    python upload_bg_video.py "C:\\Users\\kullanici\\Downloads\\somine.mp4"')
        sys.exit(1)
    upload(sys.argv[1])
