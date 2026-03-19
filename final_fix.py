import paramiko
import time

def final_fix(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    print("Bağlandı! Kesin kurulum yapılıyor (venv yöntemi)...\n")

    cmds = [
        ("venv kuruluyor...", "apt-get install -y python3-venv"),
        ("Virtual env oluşturuluyor...", "python3 -m venv /root/Yt/venv"),
        ("Flask kuruluyor (venv içinde)...", "/root/Yt/venv/bin/pip install flask requests python-dotenv"),
        ("Eski süreç siliniyor...", "pkill -f 'python3 app.py' || true"),
        ("Panel venv ile başlatılıyor...", 
         "cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &"),
    ]

    for desc, cmd in cmds:
        print(f"→ {desc}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
        stdout.channel.recv_exit_status()

    time.sleep(4)

    # Son kontrol
    stdin, stdout, _ = ssh.exec_command("ss -tlnp | grep 5000")
    port = stdout.read().decode()

    stdin2, stdout2, _ = ssh.exec_command("cat /root/Yt/output.log")
    log = stdout2.read().decode()

    print("\n=== SONUÇ ===")
    if "5000" in port:
        print(f"🚀 PANEL YAYINDA! → http://{ip}:5000")
    else:
        print(f"❌ Hata devam ediyor. Log:\n{log[-1000:] if log else 'boş'}")

    ssh.close()

if __name__ == "__main__":
    final_fix("72.60.119.24", "19981976Yt..")
