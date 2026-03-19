import paramiko
import time

def fix_502(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    
    print("Sunucuya bağlanıldı. Port düzeltiliyor...")
    
    # 1. Portu 5001'den 5000'e çek
    # (Hem sed hem de manuel kontrol garantisi için)
    ssh.exec_command("sed -i 's/port=5001/port=5000/g' /root/Yt/app.py")
    
    # 2. Süreçleri temizle
    ssh.exec_command("pkill -f 'python3 app.py' || true")
    time.sleep(2)
    
    # 3. Yeniden başlat
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    
    print("Sistem yeniden başlatıldı. 5 saniye bekleniyor...")
    time.sleep(5)
    
    # 4. Kontrol
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 5000")
    result = stdout.read().decode()
    if "5000" in result:
        print("BAŞARILI: Uygulama şu an 5000 portunda dinliyor.")
    else:
        print("HATA: Uygulama başlatılamadı or port 5000 hala kapalı.")
        stdin, stdout, stderr = ssh.exec_command("tail -n 20 /root/Yt/output.log")
        print("LOG KAYDI:")
        print(stdout.read().decode())

    ssh.close()

if __name__ == "__main__":
    fix_502("72.60.119.24", "19981976Yt..")
