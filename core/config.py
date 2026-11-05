import os
import sys
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 资源路径
MODELS_DIR = BASE_DIR / "models"
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"

for folder in [MODELS_DIR, UPLOADS_DIR, OUTPUTS_DIR, STATIC_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# 关键模型文件路径
INSWAPPER_MODEL_PATH = MODELS_DIR / "inswapper_128.onnx"
ARCFACE_MODEL_PATH = MODELS_DIR / "w600k_r50.onnx"
SCRFD_MODEL_PATH = MODELS_DIR / "scrfd_10g_bnkps.onnx"

# 获取 FFmpeg 路径
def get_ffmpeg_binary():
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    import shutil
    sys_ffmpeg = shutil.which("ffmpeg")
    return sys_ffmpeg or "ffmpeg"

FFMPEG_PATH = get_ffmpeg_binary()

# 硬件加速提供者 (Execution Providers) 探测
def detect_execution_providers():
    providers = []
    try:
        import onnxruntime as ort
        available = ort.get_available_providers()
        # 优先级：CUDA -> DirectML (支持AMD/Intel/Nvidia) -> CoreML -> CPU
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
        if "DmlExecutionProvider" in available:
            providers.append("DmlExecutionProvider")
        if "CoreMLExecutionProvider" in available:
            providers.append("CoreMLExecutionProvider")
        providers.append("CPUExecutionProvider")
    except ImportError:
        providers = ["CPUExecutionProvider"]
    return providers

DEFAULT_PROVIDERS = detect_execution_providers()

# 模型下载元信息 (国内 ModelScope / Gitee / 官方 HuggingFace 备份链接)
MODEL_SOURCES = {
    "inswapper_128.onnx": [
        "https://hf-mirror.com/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx",
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/inswapper_128.onnx"
    ],
    "scrfd_10g_bnkps.onnx": [
        "https://hf-mirror.com/ezioruan/inswapper_128.onnx/resolve/main/scrfd_10g_bnkps.onnx",
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/scrfd_10g_bnkps.onnx"
    ],
    "w600k_r50.onnx": [
        "https://hf-mirror.com/ezioruan/inswapper_128.onnx/resolve/main/w600k_r50.onnx",
        "https://huggingface.co/ezioruan/inswapper_128.onnx/resolve/main/w600k_r50.onnx"
    ]
}

