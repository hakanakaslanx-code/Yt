import paramiko
import os

def push_index(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password, timeout=10)
    sftp = ssh.open_sftp()
    
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'index.html')
    sftp.put(local, '/root/Yt/templates/index.html')
    sftp.close()
    print("✅ index.html güncellendi.")
    ssh.close()

if __name__ == "__main__":
    push_index("72.60.119.24", "19981976Yt..")
