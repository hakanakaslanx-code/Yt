import paramiko
import time

def setup_vps(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print(f"Sunucuya bağlanılıyor: {ip}...")
    try:
        ssh.connect(ip, username='root', password=password)
        print("Bağlantı başarılı! Kurulum başlatılıyor...")
        
        commands = [
            "apt update -y",
            "apt install -y python3-pip ffmpeg git",
            "git clone https://github.com/hakanakaslanx-code/Yt.git || (cd Yt && git pull)",
            "cd Yt && pip3 install flask requests moviepy replicate python-dotenv --break-system-packages"
        ]
        
        for cmd in commands:
            print(f"Çalıştırılıyor: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            # Çıktıyı bekle
            stdout.channel.recv_exit_status()
            print(f"Tamamlandı: {cmd}")
            
        print("\n--- KURULUM TAMAMLANDI! ---")
        print(f"Panel şu adreste yayında: http://{ip}:5000")
        print("Sunucuda paneli başlatmak için 'python3 Yt/app.py' komutunu kullanabilirsiniz.")
        
    except Exception as e:
        print(f"Bağlantı hatası: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    setup_vps("72.60.119.24", "19981976Yt..")
