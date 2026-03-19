import paramiko
import time
import os

def final_multi_page_deploy(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    sftp = ssh.open_sftp()

    # Klasör oluştur
    for folder in ['/root/Yt', '/root/Yt/templates']:
        try: sftp.mkdir(folder)
        except: pass

    # Dosyaları yükle
    local_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Tüm dosyaları gönder (Ana dosyalar)
    base_files = ['app.py', 'music_gen.py', 'image_gen.py', 'video_engine.py', 'requirements.txt']
    
    # Template dosyaları
    templates = ['base.html', 'dashboard.html', 'channels.html', 'forge.html', 'settings.html']
    
    print("Dosyalar yükleniyor...")
    for f in base_files:
        sftp.put(os.path.join(local_dir, f), f'/root/Yt/{f}')
        print(f"  ✅ {f}")
        
    for f in templates:
        sftp.put(os.path.join(local_dir, 'templates', f), f'/root/Yt/templates/{f}')
        print(f"  ✅ templates/{f}")
        
    sftp.close()

    # venv ile kurulum yapılıyor...
    print("\nSunucu güncelleniyor ve yeniden başlatılıyor...")
    cmds = [
        "pkill -f 'python3 app.py' || true",
        "cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > /root/Yt/output.log 2>&1 &"
    ]
    for cmd in cmds:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        stdout.channel.recv_exit_status()

    time.sleep(3)
    print("\n🚀 PANEL ÇOK SAYFALI OLARAK YAYINLANDI!")
    print(f"Adres: http://{ip}")
    ssh.close()

if __name__ == "__main__":
    final_multi_page_deploy("72.60.119.24", "19981976Yt..")
