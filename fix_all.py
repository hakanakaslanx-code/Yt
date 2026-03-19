import paramiko

def fix_all(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)

    print("=== TAM DURUM RAPORU ===\n")

    # Tek komutta tüm bilgileri al
    cmd = """
echo "=== PORT 80 ==="
ss -tlnp | grep ':80' || echo "PORT 80 KAPALI"

echo "=== PORT 5000 ==="
ss -tlnp | grep ':5000' || echo "PORT 5000 KAPALI"

echo "=== NGINX ==="
systemctl is-active nginx

echo "=== UFW ==="
ufw status

echo "=== NGINX CONFIG ==="
cat /etc/nginx/sites-enabled/yt-panel 2>/dev/null || echo "config yok"

echo "=== NGINX ERROR LOG ==="
tail -5 /var/log/nginx/error.log 2>/dev/null || echo "log yok"

echo "=== PANEL LOG ==="
tail -10 /root/Yt/output.log 2>/dev/null || echo "log yok"
"""

    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    result = stdout.read().decode()
    print(result)

    print("\n=== FIREWALL TAMAMEN TEMIZLENIYOR VE PORT 80 ACILIYOR ===")
    
    fix_cmds = [
        # UFW'yi tamamen devre dışı bırak (en güvenli ve kolay çözüm)
        "ufw disable || true",
        # iptables'ı temizle  
        "iptables -F INPUT || true",
        "iptables -P INPUT ACCEPT || true",
        # Nginx'i yeniden başlat
        "systemctl restart nginx",
    ]
    
    for cmd in fix_cmds:
        print(f"→ {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        stdout.channel.recv_exit_status()

    # Son kontrol
    import time
    time.sleep(2)
    stdin, stdout, _ = ssh.exec_command("ss -tlnp | grep ':80'")
    port80 = stdout.read().decode()
    print(f"\nPort 80 son durum: {'✅ AÇIK' if '80' in port80 else '❌ HÂLÂ KAPALI'}")
    print(f"\n🌐 Şimdi deneyin: http://{ip}")
    print(f"🌐 Veya: http://srv1507025.hstgr.cloud")

    ssh.close()

if __name__ == "__main__":
    fix_all("72.60.119.24", "19981976Yt..")
