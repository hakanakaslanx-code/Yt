import paramiko
import time

def open_port_and_restart(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    print("Bağlandı! Firewall ayarları yapılıyor...\n")

    cmds = [
        # UFW varsa 5000 portunu aç
        ("Port 5000 açılıyor (ufw)...", "ufw allow 5000/tcp || true"),
        ("UFW yeniden başlatılıyor...", "ufw reload || true"),
        # iptables ile de aç (çift güvence)
        ("iptables ile port açılıyor...", "iptables -I INPUT -p tcp --dport 5000 -j ACCEPT"),
        # Mevcut süreci durdur ve yeniden başlat
        ("Eski süreç durduruluyor...", "pkill -f 'python3 app.py' || true"),
        ("Panel yeniden başlatılıyor...", 
         "cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > /root/Yt/output.log 2>&1 &"),
    ]

    for desc, cmd in cmds:
        print(f"→ {desc}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        stdout.channel.recv_exit_status()

    time.sleep(5)

    # Kontrol
    stdin, stdout, _ = ssh.exec_command("ss -tlnp | grep 5000")
    port = stdout.read().decode()
    
    stdin2, stdout2, _ = ssh.exec_command("cat /root/Yt/output.log")
    log = stdout2.read().decode()

    print("\n=== DURUM ===")
    if "5000" in port:
        print(f"✅ Panel sunucuda çalışıyor → Port 5000 AKTİF")
        print(f"🌐 Tarayıcıdan aç: http://{ip}:5000")
    else:
        print(f"❌ Port hâlâ kapalı. Log:\n{log[-800:] if log else 'boş'}")

    ssh.close()

if __name__ == "__main__":
    open_port_and_restart("72.60.119.24", "19981976Yt..")
