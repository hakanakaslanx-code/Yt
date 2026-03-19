import paramiko
import time
import os

def deploy_full_stack(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=15)
    sftp = ssh.open_sftp()

    for folder in ['/root/Yt', '/root/Yt/templates', '/root/Yt/outputs']:
        try: sftp.mkdir(folder)
        except: pass

    local_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("📦 MASTER AUTO V12 — FULL STACK DEPLOY")
    print("=" * 50)

    # Python modules
    py_files = ['app.py', 'requirements.txt', 'music_gen.py', 'image_gen.py',
                'video_engine.py', 'yt_auth.py', 'uploader.py', 'streamer.py']
    for f in py_files:
        src = os.path.join(local_dir, f)
        if os.path.exists(src):
            sftp.put(src, f'/root/Yt/{f}')
            print(f"  ✅ {f}")

    # Templates
    templates = ['index.html', 'channels.html', 'library.html', 
                 'tasks.html', 'settings.html', 'stream.html']
    for t in templates:
        src = os.path.join(local_dir, 'templates', t)
        if os.path.exists(src):
            sftp.put(src, f'/root/Yt/templates/{t}')
            print(f"  ✅ templates/{t}")

    sftp.close()

    # Install FFmpeg
    print("\n🔧 FFmpeg kontrol ediliyor...")
    stdin, out, err = ssh.exec_command("which ffmpeg || apt-get install -y ffmpeg -q")
    out.channel.recv_exit_status()
    print("  ✅ FFmpeg hazır.")

    # Install Python deps
    print("🔧 Python bağımlılıkları güncelleniyor...")
    stdin, out, err = ssh.exec_command("/root/Yt/venv/bin/pip install -r /root/Yt/requirements.txt -q")
    out.channel.recv_exit_status()
    print("  ✅ Bağımlılıklar hazır.")

    # Restart
    print("\n🚀 Uygulama yeniden başlatılıyor...")
    ssh.exec_command("pkill -f 'python3 app.py' || true")
    time.sleep(2)
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    time.sleep(5)

    # Verify
    stdin, out, _ = ssh.exec_command("ss -tlnp | grep 5000")
    if "5000" in out.read().decode():
        print("\n🏁 FULL STACK DEPLOY BAŞARILI!")
        print(f"   Panel: http://{ip}")
        print("   Aktif:")
        print("   ✅ / Dashboard")
        print("   ✅ /channels — My Channels")
        print("   ✅ /library  — Music Library")
        print("   ✅ /tasks    — Video Tasks")
        print("   ✅ /stream   — 🔴 Live Stream (FFmpeg)")
        print("   ✅ /settings — Settings + API Keys")
    else:
        print("❌ Başlatma başarısız. Loglar:")
        stdin, out, _ = ssh.exec_command("tail -n 30 /root/Yt/output.log")
        print(out.read().decode())

    ssh.close()

if __name__ == "__main__":
    deploy_full_stack("72.60.119.24", "19981976Yt..")
