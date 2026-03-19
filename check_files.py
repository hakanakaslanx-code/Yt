import paramiko

def check_files(ip, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='root', password=password)
    
    cmds = [
        "ls -la /root/Yt",
        "ls -la /root/Yt/templates",
        "cat /root/Yt/requirements.txt",
        "tail -20 /root/Yt/output.log"
    ]
    
    print(f"Sunucuya bağlanıldı: {ip}")
    for cmd in cmds:
        print(f"\n--- KOMUT: {cmd} ---")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode())
    
    ssh.close()

if __name__ == "__main__":
    check_files("72.60.119.24", "19981976Yt..")
