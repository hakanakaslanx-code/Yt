import paramiko
import os

def pull_nginx(ip, pwd):
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(ip, username='root', password=pwd)
    
    sftp = s.open_sftp()
    local_path = os.path.join(os.path.dirname(__file__), 'nginx_default_config.txt')
    sftp.get('/etc/nginx/sites-available/default', local_path)
    sftp.close()
    s.close()
    print("Nginx config downloaded!")

if __name__ == "__main__":
    pull_nginx("72.60.119.24", "19981976Yt..")
