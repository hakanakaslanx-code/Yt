import paramiko

def full_diagnose(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    print("Bağlandı! Tam teşhis yapılıyor...\n")

    checks = [
        ("Python Panel (port 5000)", "ss -tlnp | grep 5000"),
        ("Nginx Durumu", "systemctl is-active nginx"),
        ("Nginx Port 80", "ss -tlnp | grep ':80'"),
        ("UFW Durum Detay", "ufw status verbose"),
        ("iptables INPUT Tüm Kurallar", "iptables -L INPUT -n --line-numbers"),
        ("Nginx Config Test", "nginx -t 2>&1"),
        ("Nginx Hata Logu (son 10 satır)", "tail -10 /var/log/nginx/error.log 2>/dev/null || echo 'log yok'"),
        ("Panel Çalışıyor mu (process)", "ps aux | grep python3 | grep -v grep"),
    ]

    for label, cmd in checks:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
        result = stdout.read().decode().strip()
        print(f"=== {label} ===")
        print(result if result else "(boş/yok)")
        print()

    ssh.close()

if __name__ == "__main__":
    full_diagnose("72.60.119.24", "19981976Yt..")
