#!/usr/bin/env python3
import os
import platform
import subprocess
import sys

def main():
    # 检查Python版本
    if sys.version_info < (3, 6):
        print("需要Python 3.6或更高版本")
        sys.exit(1)

    # 创建虚拟环境
    venv_dir = ".venv"
    if not os.path.exists(venv_dir):
        print("创建虚拟环境...")
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
    
    # 根据平台确定激活路径
    if platform.system() == "Windows":
        pip_path = os.path.join(venv_dir, "Scripts", "pip.exe")
        python_path = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
        python_path = os.path.join(venv_dir, "bin", "python")

    # 安装依赖
    print("安装依赖...")
    subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)

    # 运行主程序
    print("启动主程序...")
    subprocess.run([python_path, "main.py"], check=True)

if __name__ == "__main__":
    main()