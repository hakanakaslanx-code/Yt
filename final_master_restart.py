import paramiko
import time

def final_master_restart(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    
    print("Master Auto V12 Restart ediliyor...")
    ssh.exec_command("pkill -f 'python3 app.py' || true")
    time.sleep(2)
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    
    print("Bekleniyor (5sn)...")
    time.sleep(5)
    
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 5000")
    if "5000" in stdout.read().decode():
        print("✅ BAŞARILI: Sistem 5000 portunda aktif.")
    else:
        print("❌ HATA: Sistem hala kapalı.")
        stdin, stdout, stderr = ssh.exec_command("tail -n 20 /root/Yt/output.log")
        print(stdout.read().decode())
    
    ssh.close()

if __name__ == "__main__":
    final_master_restart("72.60.119.24", "19981976Yt..")
