import paramiko
import time
import os

def kill_and_deploy(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=15)
    
    print("🧹 Cleaning up old processes...")
    ssh.exec_command("pkill -f 'flask run'")
    ssh.exec_command("pkill -f 'python3 app.py'")
    time.sleep(2)
    
    print("📦 Uploading updated app.py (Port 80)...")
    sftp = ssh.open_sftp()
    local_app = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
    sftp.put(local_app, '/root/Yt/app.py')
    sftp.close()
    
    print("🚀 Starting new Panel on Port 80...")
    ssh.exec_command("cd /root/Yt && nohup /root/Yt/venv/bin/python3 app.py > output.log 2>&1 &")
    time.sleep(5)
    
    stdin, out, _ = ssh.exec_command("ss -tlnp | grep 80")
    result = out.read().decode()
    if "80" in result:
        print("✅ SUCCESS: Panel is now running exclusively on Port 80!")
        print(result)
    else:
        print("❌ FAILED to start on Port 80. Logs:")
        stdin, out, _ = ssh.exec_command("tail -n 20 /root/Yt/output.log")
        print(out.read().decode())
        
    ssh.close()

if __name__ == "__main__":
    kill_and_deploy("72.60.119.24", "19981976Yt..")
