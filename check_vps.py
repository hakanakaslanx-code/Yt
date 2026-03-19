import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('72.60.119.24', username='root', password='19981976Yt..')

print("--- PYTHON PROCESSES ---")
stdin, out, err = ssh.exec_command('ps aux | grep python')
print(out.read().decode())

print("--- PORT 80 ---")
stdin, out, err = ssh.exec_command('ss -tlnp | grep 80')
print(out.read().decode())

print("--- PORT 5000 ---")
stdin, out, err = ssh.exec_command('ss -tlnp | grep 5000')
print(out.read().decode())

ssh.close()
