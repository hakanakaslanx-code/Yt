import paramiko

def diagnose(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(ip, username='root', password=password, timeout=10)
        print("Bağlandı! Teşhis yapılıyor...\n")

        # 1. Python versiyonu
        stdin, stdout, _ = ssh.exec_command("python3 --version")
        print(f"Python: {stdout.read().decode().strip()}")

        # 2. Yt klasörü var mı
        stdin, stdout, _ = ssh.exec_command("ls ~/Yt/")
        files = stdout.read().decode().strip()
        print(f"\nYt/ klasör içeriği:\n{files}")

        # 3. app.py'yi direkt çalıştır ve hatayı al
        print("\napp.py çalıştırılıyor (hata tespiti için 5 sn)...")
        stdin, stdout, stderr = ssh.exec_command("cd ~/Yt && timeout 5 python3 app.py 2>&1 || true")
        stdout.channel.recv_exit_status()
        output = stdout.read().decode()
        print(f"\nÇIKTI:\n{output[-1500:] if len(output)>1500 else output}")

    except Exception as e:
        print(f"Hata: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    diagnose("72.60.119.24", "19981976Yt..")
