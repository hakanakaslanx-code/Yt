"""Deploy latest changes to VPS — uploads changed files and restarts app."""
import paramiko
import os
import sys
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

IP = "72.60.119.24"
PASSWORD = "19981976Yt.."
REMOTE_DIR = "/root/Yt"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

PY_FILES = [
    'app.py', 'wsgi.py', 'music_gen.py', 'image_gen.py', 'video_engine.py',
    'yt_auth.py', 'uploader.py', 'streamer.py', 'scheduler.py',
    'analytics.py', 'backup.py', 'telegram_notify.py',
]

def run(ssh, cmd, show=True):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if show and out.strip():
        print(out.strip())
    if show and err.strip():
        print("[stderr]", err.strip())
    return out, err, rc

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {IP}...")
    ssh.connect(IP, username='root', password=PASSWORD, timeout=15)
    sftp = ssh.open_sftp()

    run(ssh, f"mkdir -p {REMOTE_DIR}/templates", show=False)

    print("Uploading Python files...")
    for f in PY_FILES:
        src = os.path.join(LOCAL_DIR, f)
        if os.path.exists(src):
            sftp.put(src, f"{REMOTE_DIR}/{f}")
            print(f"  OK {f}")
        else:
            print(f"  WARN  {f} not found locally")

    print("Uploading templates...")
    tmpl_dir = os.path.join(LOCAL_DIR, 'templates')
    for t in sorted(os.listdir(tmpl_dir)):
        if t.endswith('.html'):
            sftp.put(os.path.join(tmpl_dir, t), f"{REMOTE_DIR}/templates/{t}")
            print(f"  OK templates/{t}")

    sftp.close()

    print("\nStopping old process...")
    run(ssh, "pkill -f 'gunicorn' || true", show=False)
    run(ssh, "pkill -f 'python3 app.py' || true", show=False)
    run(ssh, "pkill -f ffmpeg || true", show=False)
    time.sleep(2)

    print("Starting app (Gunicorn)...")
    # 1 worker + 4 gthread — scheduler/queue için tek process yeterli
    gunicorn_cmd = (
        f"cd {REMOTE_DIR} && nohup "
        f"{REMOTE_DIR}/venv/bin/gunicorn "
        f"-w 1 --worker-class gthread --threads 4 "
        f"-b 0.0.0.0:5000 --timeout 600 "
        f"--log-level info "
        f"wsgi:app > output.log 2>&1 &"
    )
    ssh.exec_command(gunicorn_cmd)
    time.sleep(6)

    print("Last 20 lines of log:")
    out, _, _ = run(ssh, f"tail -20 {REMOTE_DIR}/output.log")

    out2, _, _ = run(ssh, "ss -tlnp | grep 5000", show=False)
    if "5000" in out2:
        print(f"\nOK LIVE at http://{IP}")
    else:
        print("\nWARN  Port 5000 not detected — check output.log on VPS")

    ssh.close()

if __name__ == "__main__":
    deploy()
