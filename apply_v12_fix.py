import paramiko
import time

def master_v12_final_fix(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    
    print("Sunucuya bağlanıldı. Bağımlılıklar yükleniyor...")
    
    # 1. Eksik kütüphaneleri kur (MoviePy, Requests, Dotenv)
    # -q bayrağı ile sessiz kurulum
    stdin, stdout, stderr = ssh.exec_command("/root/Yt/venv/bin/pip install moviepy requests python-dotenv numpy -q")
    stdout.channel.recv_exit_status()
    print("  ✅ Bağımlılıklar yüklendi.")
    
    # 2. Port ve Süreç kontrolü (V12 Merged sürümü zaten 5000 ayarlı geldi)
    ssh.exec_command("pkill -f 'python3 app.py' || true")
    time.sleep(2)
    
    # 3. Yeniden başlat
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    print("  🚀 Master Auto V12 Yeniden Başlatıldı.")
    
    time.sleep(5)
    
    # 4. Final Port Kontrolü
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 5000")
    result = stdout.read().decode()
    if "5000" in result:
        print("\n🏁 TEBRİKLER: Sistem 5000 portunda stabil çalışıyor.")
    else:
        print("\n⚠️ HATA: Sistem hala kapalı. Loglar inceleniyor...")
        stdin, stdout, stderr = ssh.exec_command("tail -n 20 /root/Yt/output.log")
        print(stdout.read().decode())

    ssh.close()

if __name__ == "__main__":
    master_v12_final_fix("72.60.119.24", "19981976Yt..")
