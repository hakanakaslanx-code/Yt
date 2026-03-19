import paramiko
import time
import os

def pro_v5_final_deploy(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    sftp = ssh.open_sftp()

    # Klasörler (Hepsini kurduğumuzdan emin olalım)
    for folder in ['/root/Yt', '/root/Yt/templates', '/root/Yt/outputs']:
        try: sftp.mkdir(folder)
        except: pass

    # Dosyaları yükle
    local_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Tüm dosyalar (Pro sürümü V5)
    base_files = ['app.py', 'music_gen.py', 'image_gen.py', 'video_engine.py']
    templates = ['base.html', 'dashboard.html', 'channels.html', 'forge.html', 'settings.html']
    
    print("V5 - Pro Tasarım ve Motor yükleniyor...")
    for f in base_files:
        sftp.put(os.path.join(local_dir, f), f'/root/Yt/{f}')
        print(f"  ✅ {f}")
        
    for f in templates:
        sftp.put(os.path.join(local_dir, 'templates', f), f'/root/Yt/templates/{f}')
        print(f"  ✅ templates/{f}")
        
    sftp.close()

    # Kurulum yapılıyor...
    print("\nSunucu V5 moduna yükseltiliyor...")
    cmds = [
        "pkill -f 'python3 app.py' || true",
        "cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > /root/Yt/output.log 2>&1 &"
    ]
    for cmd in cmds:
        ssh.exec_command(cmd)

    time.sleep(3)
    print("\n🚀 ALLONE PRO V5 YAYINLANDI! (Freebeat AI Kalitesi)")
    print(f"Panel: http://{ip}")
    ssh.close()

if __name__ == "__main__":
    pro_v5_final_deploy("72.60.119.24", "19981976Yt..")
