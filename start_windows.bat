@echo off
chcp 65001 >nul
echo ======================================================
echo    FaceSync AI - 实时摄像头推流与视频换脸综合系统
echo ======================================================
echo [*] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 错误: 未检测到 Python，请先安装 Python 3.10 或 3.11 并添加到 PATH！
    pause
    exit /b 1
)

echo [*] 安装/检查运行依赖...
pip install -r requirements.txt

echo [*] 正在启动系统服务...
python run.py
pause
