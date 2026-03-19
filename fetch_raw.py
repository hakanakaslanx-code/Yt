import paramiko
import os

s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect('72.60.119.24', username='root', password='19981976Yt..')

s.exec_command('curl -s http://127.0.0.1:5000 > /root/raw_index.html')

sftp = s.open_sftp()
local_path = os.path.join(os.path.dirname(__file__), 'raw_index.html')
sftp.get('/root/raw_index.html', local_path)
sftp.close()
s.close()
