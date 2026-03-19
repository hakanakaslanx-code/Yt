import paramiko
import time
import os

def final_v12_restore_deploy(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    sftp = ssh.open_sftp()

    # Klasörler
    for folder in ['/root/Yt', '/root/Yt/templates', '/root/Yt/outputs']:
        try: sftp.mkdir(folder)
        except: pass

    # Yerel Dosya Yolları (Kullanıcının gösterdiği klasör)
    local_yt_dir = r"C:\Users\socia\Documents\GitHub\Yt"
    local_automation_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("MASTER AUTO V12 - Restorasyon Başlıyor...")

    # 1. TEMPLATES: Yerel index.html'i yükle
    sftp.put(os.path.join(local_yt_dir, 'templates', 'index.html'), '/root/Yt/templates/index.html')
    print("  ✅ templates/index.html (Geri yüklendi)")

    # 2. BACKEND: Merged app.py'yi yükle
    sftp.put(os.path.join(local_automation_dir, 'app_merged_v12.py'), '/root/Yt/app.py')
    print("  ✅ app.py (Merged V12 yüklendi)")

    # 3. ENGINE: Pro Video Engine & Music Gen yükle
    # (Buradaki video_engine'da zoom/progress bar özellikleri var)
    engine_files = ['video_engine.py', 'music_gen.py', 'image_gen.py']
    for f in engine_files:
        sftp.put(os.path.join(local_automation_dir, f), f'/root/Yt/{f}')
        print(f"  ✅ {f} (Engine güncellendi)")

    sftp.close()

    # Restart
    print("\nServisler yeniden başlatılıyor...")
    cmds = [
        "pkill -f 'python3 app.py' || true",
        "cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &"
    ]
    for cmd in cmds:
        ssh.exec_command(cmd)

    time.sleep(3)
    print("\n🏁 MASTER AUTO V12 BAŞARIYLA GERİ YÜKLENDİ VE AKTİF EDİLDİ!")
    print(f"Panel: http://{ip}")
    ssh.close()

if __name__ == "__main__":
    final_v12_restore_deploy("72.60.119.24", "19981976Yt..")
