import paramiko
import time

def fix_and_start(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(ip, username='root', password=password, timeout=10)
        print("Bağlandı! Sorun gideriliyor ve panel yeniden başlatılıyor...")

        steps = [
            ("Sistem güncelleniyor...", "apt-get update -qq"),
            ("Gerekli araçlar kuruluyor...", "apt-get install -y python3-pip ffmpeg python3-dev build-essential"),
            ("Pip güncelleniyor...", "pip3 install --upgrade pip"),
            ("Kütüphaneler kuruluyor...", "pip3 install flask requests python-dotenv --break-system-packages"),
            ("Kodlar güncelleniyor...", "cd Yt && git pull origin main || (cd ~ && rm -rf Yt && git clone https://github.com/hakanakaslanx-code/Yt.git)"),
            ("Eski süreçler durduruluyor...", "pkill -f 'python3 app.py' || true"),
            ("Panel başlatılıyor...", "cd ~/Yt && nohup python3 app.py > output.log 2>&1 &"),
        ]

        for desc, cmd in steps:
            print(f"→ {desc}")
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
            stdout.channel.recv_exit_status()

        time.sleep(4)

        # Kontrol
        stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 5000")
        port_check = stdout.read().decode()

        stdin2, stdout2, stderr2 = ssh.exec_command("cat ~/Yt/output.log")
        log = stdout2.read().decode()

        print("\n=== DURUM ===")
        if "5000" in port_check:
            print(f"Panel: ✅ AKTİF - http://{ip}:5000")
        else:
            print("Panel: ❌ Hâlâ başlamadı. Log:")
            print(log[-800:] if log else "(boş log)")

    except Exception as e:
        print(f"Hata: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    fix_and_start("72.60.119.24", "19981976Yt..")
