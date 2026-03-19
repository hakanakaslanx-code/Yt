import paramiko
import time

def deploy_direct(ip, password):
    """
    GitHub yerine dosyaları doğrudan SCP ile sunucuya kopyalar.
    """
    import os
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    
    # SFTP bağlantısı
    sftp = ssh.open_sftp()
    
    # Hedef klasörü oluştur
    try:
        sftp.mkdir('/root/Yt')
    except:
        pass
    try:
        sftp.mkdir('/root/Yt/templates')
    except:
        pass

    # Yüklenecek dosyalar
    local_dir = os.path.dirname(os.path.abspath(__file__))
    files = [
        ('app.py', '/root/Yt/app.py'),
        ('music_gen.py', '/root/Yt/music_gen.py'),
        ('image_gen.py', '/root/Yt/image_gen.py'),
        ('video_engine.py', '/root/Yt/video_engine.py'),
        ('requirements.txt', '/root/Yt/requirements.txt'),
        ('templates/index.html', '/root/Yt/templates/index.html'),
    ]
    
    print("Dosyalar sunucuya yükleniyor...")
    for local, remote in files:
        local_path = os.path.join(local_dir, local)
        sftp.put(local_path, remote)
        print(f"  ✅ {local}")
    
    sftp.close()
    print("\nTüm dosyalar yüklendi! Kütüphaneler kuruluyor...")
    
    # Kütüphaneleri kur
    stdin, stdout, stderr = ssh.exec_command(
        "pip3 install flask requests python-dotenv --break-system-packages --quiet",
        timeout=120
    )
    stdout.channel.recv_exit_status()
    print("Kütüphaneler hazır!")
    
    # Eski süreci öldür
    ssh.exec_command("pkill -f 'python3 app.py' || true")
    time.sleep(1)
    
    # Panel başlat
    ssh.exec_command("cd /root/Yt && nohup python3 app.py > output.log 2>&1 &")
    time.sleep(4)
    
    # Kontrol
    stdin, stdout, _ = ssh.exec_command("ss -tlnp | grep 5000")
    port = stdout.read().decode()
    
    if "5000" in port:
        print(f"\n🚀 PANEL YAYINDA! http://{ip}:5000")
    else:
        stdin, stdout, _ = ssh.exec_command("cat /root/Yt/output.log")
        log = stdout.read().decode()
        print(f"\n❌ Panel başlamadı. Log:\n{log}")
    
    ssh.close()

if __name__ == "__main__":
    deploy_direct("72.60.119.24", "19981976Yt..")
