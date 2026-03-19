import paramiko
import time
import os

def full_deploy(ip, password):
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
    files = [
        ('app.py', '/root/Yt/app.py'),
        ('music_gen.py', '/root/Yt/music_gen.py'),
        ('image_gen.py', '/root/Yt/image_gen.py'),
        ('video_engine.py', '/root/Yt/video_engine.py'),
        ('requirements.txt', '/root/Yt/requirements.txt'),
        ('templates/index.html', '/root/Yt/templates/index.html'),
    ]
    print("Dosyalar yükleniyor...")
    for local, remote in files:
        sftp.put(os.path.join(local_dir, local), remote)
        print(f"  ✅ {local}")
    sftp.close()

    # venv oluştur ve flask kur
    print("\nvenv ile kurulum yapılıyor...")
    cmds = [
        "apt-get install -y python3-venv -qq",
        "python3 -m venv /root/Yt/venv",
        "/root/Yt/venv/bin/pip install flask python-dotenv -q",
        "pkill -f 'python3 app.py' || true",
        "cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > /root/Yt/output.log 2>&1 &"
    ]
    for cmd in cmds:
        print(f"→ {cmd[:50]}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
        stdout.channel.recv_exit_status()

    time.sleep(5)

    # Kontrol
    stdin, stdout, _ = ssh.exec_command("ss -tlnp | grep 5000")
    port = stdout.read().decode()
    stdin2, stdout2, _ = ssh.exec_command("cat /root/Yt/output.log")
    log = stdout2.read().decode()

    print("\n=== SONUÇ ===")
    if "5000" in port:
        print(f"🚀 PANEL YAYINDA! → http://{ip}:5000")
    else:
        print(f"❌ Hata:\n{log[-1200:] if log else 'boş log'}")

    ssh.close()

if __name__ == "__main__":
    full_deploy("72.60.119.24", "19981976Yt..")
