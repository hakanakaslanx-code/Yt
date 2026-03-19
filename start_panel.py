import paramiko
import time

def start_server(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(ip, username='root', password=password)
        print("Bağlantı başarılı! Panel başlatılıyor...")
        
        # Ekran arkasında çalışması için nohup veya screen kullanıyoruz
        # 5000 portunu dışarı açıyoruz.
        cmd = "cd Yt && nohup python3 app.py > output.log 2>&1 &"
        ssh.exec_command(cmd)
        
        # Sunucunun başlaması için kısa bir bekleyiş
        time.sleep(3)
        print("\n--- TEBRİKLER! SISTEM YAYINDA ---")
        print(f"Adres: http://{ip}:5000")
        print("Şu an telefonundan veya bilgisayarından bu adrese girebilirsin.")
        
    except Exception as e:
        print(f"Hata: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    start_server("72.60.119.24", "19981976Yt..")
