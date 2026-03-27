
import paramiko
import os
import time

IP = "72.60.119.24"
PASSWORD = "19981976Yt.."
REMOTE_DIR = "/root/Yt"
LOCAL_DIR = r"C:\Users\kusht\OneDrive\Documents\GitHub\yt\Yt"

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {IP}...")
        ssh.connect(IP, username='root', password=PASSWORD, timeout=15)
        sftp = ssh.open_sftp()

        print("--- Cleaning old processes ---")
        ssh.exec_command("fuser -k 5000/tcp 2>/dev/null || true")
        ssh.exec_command("pkill -f 'python3 app.py' 2>/dev/null || true")
        time.sleep(2)

        # Ensure remote directory exists
        ssh.exec_command(f"mkdir -p {REMOTE_DIR}/templates")

        # Files to sync
        files = [
            'app.py', 'music_gen.py', 'image_gen.py',
            'video_engine.py', 'yt_auth.py', 'uploader.py',
            'streamer.py', 'requirements.txt', 'raw_index.html'
        ]

        print("--- Uploading files ---")
        for f in files:
            src = os.path.join(LOCAL_DIR, f)
            if os.path.exists(src):
                sftp.put(src, f"{REMOTE_DIR}/{f}")
                print(f"  OK: {f}")

        # Upload templates
        local_templates = os.path.join(LOCAL_DIR, 'templates')
        if os.path.exists(local_templates):
            for t in os.listdir(local_templates):
                if t.endswith('.html'):
                    sftp.put(os.path.join(local_templates, t), f"{REMOTE_DIR}/templates/{t}")
                    print(f"  OK: templates/{t}")

        sftp.close()

        print("--- Installing dependencies ---")
        cmd_install = f"{REMOTE_DIR}/venv/bin/pip install -r {REMOTE_DIR}/requirements.txt -q"
        stdin, stdout, stderr = ssh.exec_command(cmd_install)
        stdout.channel.recv_exit_status()

        print("--- Starting application ---")
        cmd_start = f"cd {REMOTE_DIR} && nohup {REMOTE_DIR}/venv/bin/python3 app.py > output.log 2>&1 &"
        ssh.exec_command(cmd_start)
        time.sleep(3)

        print("--- Checking logs ---")
        stdin, stdout, stderr = ssh.exec_command(f"tail -n 20 {REMOTE_DIR}/output.log")
        print(stdout.read().decode())

        print("--- Deployment complete ---")
        stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 5000")
        output = stdout.read().decode()
        if "5000" in output:
            print(f"DONE: Application is LIVE at http://{IP}")
        else:
            print("WARNING: Port 5000 not detected. Check output.log on VPS.")

    except Exception as e:
        print(f"ERROR during deployment: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    deploy()
