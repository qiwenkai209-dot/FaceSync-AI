#!/usr/bin/env bash
set -e

echo "======================================================"
echo "   FaceSync AI - 实时摄像头推流与视频换脸综合系统"
echo "======================================================"

if ! command -v python3 &> /dev/null; then
    echo "[!] 错误: 未检测到 python3，请先安装 Python 3.10+！"
    exit 1
fi

echo "[*] 安装/检查运行依赖..."
pip3 install -r requirements.txt

echo "[*] 启动服务..."
python3 run.py
