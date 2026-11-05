#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# FaceSync AI - 安卓手机 (Termux) 纯本地独立运行一键部署脚本
# 适用环境：任意 64位 安卓手机 (Android 8.0 ~ 15)
# 无需电脑，无需连接局域网，手机自己当服务器 + 手机浏览器直接运行！
# ==============================================================================

set -e

echo "=========================================================="
echo "    🚀 正在为安卓手机部署 FaceSync AI 纯本地换脸引擎 🚀"
echo "=========================================================="

echo "[1/4] 更新 Termux 基础软件包..."
pkg update -y && pkg upgrade -y

echo "[2/4] 安装 Python、FFmpeg、Clang编译链与图像基础库..."
pkg install -y python ffmpeg libjpeg-turbo libpng clang make git tur-repo
pkg install -y python-numpy python-pillow

echo "[3/4] 安装 Python 依赖包 (ARM64 优化版)..."
pip install --upgrade pip
pip install fastapi uvicorn websockets python-multipart requests tqdm
pip install opencv-python-headless

echo "[*] 安装 ONNX Runtime (ARM64 / CPU / NNAPI 加速)..."
# Termux aarch64 环境下安装 onnxruntime
pip install onnxruntime || {
    echo "[!] 提示: 若 pip 在当前平台预编译轮子受限，正在从 Termux 官方源补全..."
    pkg install -y python-onnxruntime || true
}

echo "[4/4] 部署完成！"
echo "=========================================================="
echo "  运行命令: python run.py"
echo "  在手机浏览器中打开: http://127.0.0.1:8000"
echo "  即可完全不依赖电脑，直接使用手机摄像头实时换脸与生成视频！"
echo "=========================================================="

