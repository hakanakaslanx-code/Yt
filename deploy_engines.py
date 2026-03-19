import paramiko
import time
import os

def deploy_engines(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=15)
    sftp = ssh.open_sftp()

    local_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("📦 DEPLOYING AI ENGINE UPGRADES")
    print("=" * 50)

    # Updated Python modules
    py_files = ['app.py', 'image_gen.py', 'video_engine.py']
    for f in py_files:
        src = os.path.join(local_dir, f)
        if os.path.exists(src):
            sftp.put(src, f'/root/Yt/{f}')
            print(f"  ✅ Uploaded {f}")

    sftp.close()

    # Restart
    print("\n🚀 Uygulama yeniden başlatılıyor...")
    ssh.exec_command("pkill -f 'python3 app.py' || true")
    time.sleep(2)
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    time.sleep(5)

    # Verify
    stdin, out, _ = ssh.exec_command("ss -tlnp | grep 5000")
    if "5000" in out.read().decode():
        print("\n🏁 ENGINE UPGRADE BAŞARILI!")
    else:
        print("❌ Başlatma başarısız. Loglar:")
        stdin, out, _ = ssh.exec_command("tail -n 20 /root/Yt/output.log")
        print(out.read().decode())

    ssh.close()

if __name__ == "__main__":
    deploy_engines("72.60.119.24", "19981976Yt..")
