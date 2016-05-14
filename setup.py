import subprocess
import shutil

dist_dir = r'./DeployIT'
subprocess.call(['pyinstaller', '--onefile', '--icon=./img/deploy.ico', '--distpath=%s' % dist_dir, './DeployIT.py'])

shutil.copytree(r'./config', dist_dir+r'/config')
shutil.copy(r'./help.txt', dist_dir)
shutil.copy(r'./README.txt', dist_dir)
