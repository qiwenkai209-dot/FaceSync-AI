import os
import sys
import socket
import uvicorn
from pathlib import Path

def print_banner(lan_ip: str, port: int):
    print("=" * 70)
    print("      🚀 FaceSync AI - 实时摄像头推流与视频换脸综合系统 🚀")
    print("=" * 70)
    print(" [核心技术] 基于 InsightFace (Inswapper 128) + ONNX Runtime 加速")
    print(f" [PC控制台] http://127.0.0.1:{port} 或 http://{lan_ip}:{port}")
    print(f" [手机推流] http://{lan_ip}:{port}/mobile (同一 Wi-Fi 下扫码直连)")
    print("-" * 70)
    print(" [功能特性]")
    print("  1. 手机端浏览器直接调用手机前/后置摄像头采集，超低延迟实时换脸")
    print("  2. 本地电脑摄像头 / RTSP 视频流直连")
    print("  3. 离线视频导入逐帧换脸，支持实时动态预览视窗与原声音频保留")
    print("  4. 智能硬件自适应 (DirectML / CUDA / CPU 降级容错)")
    print("=" * 70)

def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def check_models_background():
    """非阻塞触发模型检测"""
    from core.config import INSWAPPER_MODEL_PATH
    if not INSWAPPER_MODEL_PATH.exists():
        print("\n[*] 提示: 检测到初次运行，核心 ONNX 权重文件尚未下载。")
        print("    系统当前处于【自适应演示融合模式】，基础推流与视频链路完全畅通！")
        print("    若需下载 500MB 高精度官方 Inswapper 权重，可单独运行:")
        print("    python core/download_models.py\n")

if __name__ == "__main__":
    lan_ip = get_lan_ip()
    port = 8000
    print_banner(lan_ip, port)
    check_models_background()
    
    # 启动异步 Web 服务
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, log_level="info")

