import paramiko
import time
import os

def mega_v4_deploy(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    sftp = ssh.open_sftp()

    # Klasörler
    for folder in ['/root/Yt', '/root/Yt/templates']:
        try: sftp.mkdir(folder)
        except: pass

    # Dosyaları yükle
    local_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Tüm dosyalar (Pro sürümleri)
    base_files = ['app.py', 'music_gen.py', 'image_gen.py', 'video_engine.py', 'requirements.txt']
    
    # Template dosyaları
    templates = ['base.html', 'dashboard.html', 'channels.html', 'forge.html', 'settings.html']
    
    print("Dosyalar Pro sürümüne yükseltiliyor...")
    for f in base_files:
        sftp.put(os.path.join(local_dir, f), f'/root/Yt/{f}')
        print(f"  ✅ {f}")
        
    for f in templates:
        sftp.put(os.path.join(local_dir, 'templates', f), f'/root/Yt/templates/{f}')
        print(f"  ✅ templates/{f}")
        
    sftp.close()

    # venv ile kurulum yapılıyor...
    print("\nMotor güncelleniyor ve yeniden başlatılıyor...")
    cmds = [
        # Gerekli ek kütüphaneleri (MoviePy yanındakileri) kur
        "/root/Yt/venv/bin/pip install moviepy numpy imageio -q",
        "pkill -f 'python3 app.py' || true",
        "cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > /root/Yt/output.log 2>&1 &"
    ]
    for cmd in cmds:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
        stdout.channel.recv_exit_status()

    time.sleep(3)
    print("\n--- TEBRİKLER! TÜM SİSTEM BAŞARIYLA BAŞLATILDI ---")
    print(f"Adres: http://{ip}")
    ssh.close()

if __name__ == "__main__":
    mega_v4_deploy("72.60.119.24", "19981976Yt..")
