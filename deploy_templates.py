import paramiko
import os

def push_all_templates(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=15)
    sftp = ssh.open_sftp()

    local_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Push ALL templates in the templates folder
    templates_dir = os.path.join(local_dir, 'templates')
    for t in os.listdir(templates_dir):
        if t.endswith('.html'):
            local_path = os.path.join(templates_dir, t)
            remote_path = f'/root/Yt/templates/{t}'
            sftp.put(local_path, remote_path)
            print(f"✅ Uploaded templates/{t}")

    sftp.close()
    
    # Restart app to be safe
    ssh.exec_command("pkill -f 'python3 app.py'")
    import time; time.sleep(2)
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    
    ssh.close()
    print("✅ All templates deployed and app restarted.")

if __name__ == "__main__":
    push_all_templates("72.60.119.24", "19981976Yt..")
