FROM python:3.11-slim

# 安装系统级音视频与图形库依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制全部源码
COPY . .

# 暴露服务端口
EXPOSE 8000

# 默认启动命令
CMD ["python", "run.py"]
