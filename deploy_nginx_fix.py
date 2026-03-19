import paramiko
import time
import os

def clean_deploy(ip, pwd):
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(ip, username='root', password=pwd)

    print("Killing existing python/flask...")
    s.exec_command("pkill -f 'flask'")
    s.exec_command("pkill -f 'python3 app.py'")
    time.sleep(2)

    sftp = s.open_sftp()
    sftp.put(os.path.join(os.path.dirname(__file__), 'app.py'), '/root/Yt/app.py')
    sftp.close()

    print("Starting app.py on port 5000...")
    s.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    time.sleep(4)

    print("Restarting NGINX...")
    s.exec_command("systemctl restart nginx")
    time.sleep(2)

    stdin, out, _ = s.exec_command("ss -tlnp | grep 5000")
    if "5000" in out.read().decode():
        print("✅ SUCCESS! app.py is loaded on 5000, Nginx is handling port 80.")
    s.close()

if __name__ == "__main__":
    clean_deploy("72.60.119.24", "19981976Yt..")
