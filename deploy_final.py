import paramiko
import time
import os

def deploy_final(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=15)
    sftp = ssh.open_sftp()

    local_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("🔧 FULL SYSTEM AUDIT DEPLOY")
    print("=" * 50)

    # 1) Kill all Python processes
    print("\n🧹 Killing ALL old python processes...")
    ssh.exec_command("fuser -k 5000/tcp 2>/dev/null || true")
    ssh.exec_command("pkill -f 'python3 app.py' 2>/dev/null || true")
    ssh.exec_command("pkill -f 'flask' 2>/dev/null || true")
    time.sleep(3)

    # 2) Upload all Python files
    py_files = ['app.py', 'music_gen.py', 'image_gen.py',
                'video_engine.py', 'yt_auth.py', 'uploader.py',
                'streamer.py', 'requirements.txt']
    for f in py_files:
        src = os.path.join(local_dir, f)
        if os.path.exists(src):
            sftp.put(src, f'/root/Yt/{f}')
            print(f"  ✅ {f}")

    # 3) Upload ALL templates
    templates_dir = os.path.join(local_dir, 'templates')
    for t in os.listdir(templates_dir):
        if t.endswith('.html'):
            sftp.put(os.path.join(templates_dir, t), f'/root/Yt/templates/{t}')
            print(f"  ✅ templates/{t}")

    sftp.close()

    # 4) Install deps
    print("\n📦 Installing dependencies...")
    stdin, out, err = ssh.exec_command("/root/Yt/venv/bin/pip install -r /root/Yt/requirements.txt -q 2>&1")
    out.channel.recv_exit_status()

    # 5) Start fresh
    print("🚀 Starting clean app.py...")
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    time.sleep(5)

    # 6) Verify
    stdin, out, _ = ssh.exec_command("tail -n 15 /root/Yt/output.log")
    log = out.read().decode()
    print("\n📋 Startup Log:")
    print(log)

    stdin, out, _ = ssh.exec_command("ss -tlnp | grep 5000")
    if "5000" in out.read().decode():
        print("\n✅ SYSTEM AUDIT DEPLOY SUCCESS!")
        print(f"   Panel: http://{ip}")
    else:
        print("\n❌ FAILED — check logs above")

    ssh.close()

if __name__ == "__main__":
    deploy_final("72.60.119.24", "19981976Yt..")
