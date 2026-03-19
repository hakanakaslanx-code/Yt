import paramiko

s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('72.60.119.24', username='root', password='19981976Yt..')

stdin, out, err = s.exec_command('curl -s http://127.0.0.1:5000')
print(out.read().decode())
