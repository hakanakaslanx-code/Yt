import paramiko
import time

def setup_nginx(ip, password, domain):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    print(f"Bağlandı! Nginx kuruluyor → {domain}\n")

    nginx_config = f"""server {{
    listen 80;
    server_name {domain} {ip};

    location / {{
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}"""

    cmds = [
        ("Nginx kuruluyor...", "apt-get install -y nginx"),
        ("Eski süreç durduruluyor...", "pkill -f 'python3 app.py' || true"),
        ("Panel yeniden başlatılıyor...", 
         "cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > /root/Yt/output.log 2>&1 &"),
    ]

    for desc, cmd in cmds:
        print(f"→ {desc}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
        stdout.channel.recv_exit_status()

    # Nginx config yaz
    print("→ Nginx ayarları yapılandırılıyor...")
    sftp = ssh.open_sftp()
    with sftp.open('/etc/nginx/sites-available/yt-panel', 'w') as f:
        f.write(nginx_config)
    sftp.close()

    setup_cmds = [
        ("Nginx site aktif ediliyor...", 
         "ln -sf /etc/nginx/sites-available/yt-panel /etc/nginx/sites-enabled/yt-panel"),
        ("Default site kaldırılıyor...", 
         "rm -f /etc/nginx/sites-enabled/default"),
        ("Nginx test yapılıyor...", "nginx -t"),
        ("Nginx yeniden başlatılıyor...", "systemctl restart nginx"),
        ("Port 80 açılıyor...", "ufw allow 80/tcp || true ; iptables -I INPUT -p tcp --dport 80 -j ACCEPT"),
    ]

    for desc, cmd in setup_cmds:
        print(f"→ {desc}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        stdout.channel.recv_exit_status()

    time.sleep(3)

    # Son kontrol
    stdin, stdout, _ = ssh.exec_command("systemctl is-active nginx")
    nginx_status = stdout.read().decode().strip()

    stdin2, stdout2, _ = ssh.exec_command("ss -tlnp | grep 5000")
    panel_status = stdout2.read().decode()

    print("\n=== SONUÇ ===")
    print(f"Nginx: {'✅ AKTİF' if nginx_status == 'active' else '❌ ' + nginx_status}")
    print(f"Panel (5000): {'✅ AKTİF' if '5000' in panel_status else '❌ KAPALI'}")
    if nginx_status == 'active' and '5000' in panel_status:
        print(f"\n🚀 YAYINDAYİZ! → http://{domain}")
    
    ssh.close()

if __name__ == "__main__":
    setup_nginx("72.60.119.24", "19981976Yt..", "srv1507025.hstgr.cloud")
