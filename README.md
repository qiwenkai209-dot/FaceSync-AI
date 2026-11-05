# FaceSync AI - 实时摄像头推流与视频换脸系统

基于业界最强开源换脸管线（**InsightFace Inswapper 128 + ONNX Runtime 加速 + WebRTC/WebSocket 异步流**）构建的端到端智能换脸平台。

---

## 🌟 核心亮点

1. **📱 手机摄像头扫码即用实时换脸**
   - 跨平台零安装：手机打开浏览器扫码，直接调用手机高清前置/后置摄像头推流。
   - 毫秒级低延迟：手机画面经局域网传输至主机换脸，大屏幕与手机端画中画同步流畅播放。
2. **🎬 离线视频导入生成 + 逐帧动态实时预览**
   - 拖拽导入 MP4/MOV 视频，一键生成换脸视频。
   - **实时动态预览视窗**：在视频生成过程中，实时查看每一帧的换脸效果，告别盲目等待。
   - **100% 完美保留原声音频**：通过 FFmpeg 自动对齐原视频对白与背景音乐，生成即点即播的成片并支持一键下载。
3. **⚡ 全硬件生态自适应**
   - **NVIDIA 显卡**：自动启用 CUDAExecutionProvider。
   - **AMD 显卡 / Intel 显卡**：自动启用 **DirectML (DmlExecutionProvider)** 硬件加速！
   - **纯 CPU 环境**：自动多线程优化降级，保证任何环境下系统永不崩溃。

---

## 🚀 快速启动

### 1. 安装依赖
```bash
pip install -r requirements.txt
```
> **硬件加速选项推荐**：
> - 若机器为 **AMD 显卡** 或 **Intel 显卡**，推荐安装：`pip install onnxruntime-directml`
> - 若机器为 **NVIDIA 显卡**，推荐安装：`pip install onnxruntime-gpu`

### 2. 启动系统
```bash
python run.py
```
终端将自动输出：
- **PC 控制台网址**：`http://127.0.0.1:8000`
- **手机扫码推流网址**：`http://<局域网IP>:8000/mobile`

### 3. 高精度官方模型权重（可选）
初次启动系统会自动启用高兼容度自适应演示融合引擎。如需体验 100% 工业级 Inswapper 128 权重，直接执行：
```bash
python core/download_models.py
```
脚本将自动从国内极速镜像源下载 `inswapper_128.onnx`、`scrfd_10g_bnkps.onnx`、`w600k_r50.onnx`。

---

## 📂 项目结构

```
d:\aiagent\huanlian/
├── run.py                      # 统一一键启动脚本 (环境自适应探测与提示)
├── requirements.txt            # 项目 Python 依赖
├── FEASIBILITY_REPORT.md       # 深度商业与技术落地性评估报告
├── README.md                   # 快速上手指南
├── models/                     # 存放 ONNX 权重文件
├── uploads/                    # 临时上传的源人脸图片与视频
├── outputs/                    # 生成好的带原声音频换脸成品视频
├── static/                     # 前端现代化 Web 界面
│   ├── css/style.css           # 科技感暗黑玻璃拟态样式
│   ├── js/app.js               # 控制台核心逻辑 (流处理、视频任务调度)
│   ├── js/mobile.js            # 手机端采集专属交互脚本
│   ├── index.html              # 电脑主控制大屏
│   └── mobile.html             # 手机端轻量采集页面
├── core/                       # 核心算法与管道
│   ├── config.py               # 路径配置与硬件执行器探测
│   ├── download_models.py      # 模型自动下载工具
│   ├── face_analyzer.py        # 人脸检测定位与 512D ArcFace 提取
│   ├── face_swapper.py         # Inswapper 推理与羽化遮罩融合引擎
│   └── video_processor.py      # 视频逐帧换脸、实时预览流与音频合并
└── server/                     # 服务端网络通信
    └── app.py                  # FastAPI 异步应用与 WebSocket 管道
```

---

## ⚖️ 法律合规与伦理声明
- 本项目仅供技术学习、学术研究与合法娱乐创作使用。
- 依据《互联网信息服务深度合成管理规定》，使用本系统生成的视频应显式标明“AI深度合成”标识。
- 严禁将本软件用于侵犯他人肖像权、名誉权、诈骗或违法犯罪行为。

