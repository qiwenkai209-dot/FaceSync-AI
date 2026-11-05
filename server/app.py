import os
import io
import time
import json
import socket
import asyncio
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response, JSONResponse

from core.config import BASE_DIR, UPLOADS_DIR, OUTPUTS_DIR, STATIC_DIR, DEFAULT_PROVIDERS, INSWAPPER_MODEL_PATH
from core.face_analyzer import FaceAnalyzer
from core.face_swapper import FaceSwapper
from core.video_processor import VideoProcessor

app = FastAPI(title="FaceSync AI - 实时摄像头与视频换脸系统")

# 挂载静态资源
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# 初始化核心引擎
analyzer = FaceAnalyzer()
swapper = FaceSwapper()
video_proc = VideoProcessor(analyzer, swapper)

# 全局状态管理
CURRENT_SOURCE_FACE: Dict[str, Any] = {
    "id": None,
    "image_path": None,
    "crop_path": None,
    "crop_image": None,
    "embedding": None,
    "name": "未选择"
}

# WebSocket 连接池
active_screen_clients = set()
active_stream_sources = set()

def get_lan_ip() -> str:
    """获取本机首选局域网 IP，便于手机扫码访问"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LAN_IP = get_lan_ip()

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    return FileResponse(str(index_file))

@app.get("/mobile", response_class=HTMLResponse)
async def serve_mobile():
    mobile_file = STATIC_DIR / "mobile.html"
    return FileResponse(str(mobile_file))

@app.get("/api/system_status")
async def get_system_status():
    """获取当前系统运行状态与硬件信息"""
    model_loaded = INSWAPPER_MODEL_PATH.exists() and swapper.is_onnx_ready
    return {
        "lan_ip": LAN_IP,
        "port": 8000,
        "mobile_url": f"http://{LAN_IP}:8000/mobile",
        "providers": DEFAULT_PROVIDERS,
        "acceleration": "DirectML (AMD/Intel显卡加速)" if "DmlExecutionProvider" in DEFAULT_PROVIDERS else (
            "CUDA (NVIDIA 硬件加速)" if "CUDAExecutionProvider" in DEFAULT_PROVIDERS else "CPU (多线程优化)"
        ),
        "model_loaded": model_loaded,
        "current_source": {
            "name": CURRENT_SOURCE_FACE["name"],
            "crop_path": CURRENT_SOURCE_FACE["crop_path"],
            "has_face": CURRENT_SOURCE_FACE["embedding"] is not None
        }
    }

@app.post("/api/upload_source_face")
async def upload_source_face(file: UploadFile = File(...)):
    """上传源人脸图片并提取特征与面部对齐切片"""
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="图片格式无法识别")

        # 保存源图
        file_ext = Path(file.filename).suffix or ".jpg"
        file_name = f"source_{int(time.time()*1000)}{file_ext}"
        saved_path = UPLOADS_DIR / file_name
        with open(saved_path, "wb") as f:
            f.write(contents)

        # 检测人脸
        faces = analyzer.detect_faces(img)
        if not faces:
            return JSONResponse(status_code=422, content={"success": False, "message": "未在上传图片中检测到清晰人脸，请重试"})

        # 取最大的一张人脸提取特征
        face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
        emb = analyzer.get_face_embedding(img, face)

        # 裁剪 128x128 人脸切片供展示和备用融合
        crop_path = UPLOADS_DIR / f"crop_{file_name}"
        if face.affine_matrix is not None:
            crop_img = cv2.warpAffine(img, face.affine_matrix, (128, 128), borderMode=cv2.BORDER_REFLECT101)
        else:
            x1, y1, x2, y2 = [int(v) for v in face.bbox]
            crop_img = cv2.resize(img[max(0, y1):y2, max(0, x1):x2], (128, 128))

        cv2.imwrite(str(crop_path), crop_img)

        # 更新全局选中人脸
        CURRENT_SOURCE_FACE.update({
            "id": file_name,
            "image_path": f"/uploads/{file_name}",
            "crop_path": f"/uploads/crop_{file_name}",
            "crop_image": crop_img,
            "embedding": emb,
            "name": file.filename
        })

        return {
            "success": True,
            "name": file.filename,
            "crop_url": f"/uploads/crop_{file_name}",
            "message": "源人脸特征提取成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/video/start_swap")
async def start_video_swap(file: UploadFile = File(...)):
    """上传视频并启动换脸生成任务"""
    if CURRENT_SOURCE_FACE["embedding"] is None:
        return JSONResponse(status_code=400, content={"success": False, "message": "请先上传一张源人脸图片"})

    video_ext = Path(file.filename).suffix or ".mp4"
    saved_filename = f"video_in_{int(time.time()*1000)}{video_ext}"
    saved_path = UPLOADS_DIR / saved_filename

    contents = await file.read()
    with open(saved_path, "wb") as f:
        f.write(contents)

    task = video_proc.create_task(
        str(saved_path),
        {
            "embedding": CURRENT_SOURCE_FACE["embedding"],
            "crop": CURRENT_SOURCE_FACE["crop_image"]
        }
    )
    video_proc.start_task_async(task)

    return {
        "success": True,
        "task_id": task.task_id,
        "message": "视频换脸任务已启动"
    }

@app.get("/api/video/status/{task_id}")
async def get_video_status(task_id: str):
    """获取视频处理任务实时状态"""
    task = video_proc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "current_frame": task.current_frame,
        "total_frames": task.total_frames,
        "fps": task.fps,
        "eta_seconds": task.eta_seconds,
        "output_url": task.output_video_path,
        "error": task.error_message
    }

@app.get("/api/video/preview/{task_id}")
async def get_video_preview_frame(task_id: str):
    """获取视频正在处理的最新帧图像用于实时预览"""
    task = video_proc.get_task(task_id)
    if not task or not task.latest_preview_frame_jpeg:
        # 返回透明占位
        return Response(content=b"", media_type="image/jpeg")
    return Response(content=task.latest_preview_frame_jpeg, media_type="image/jpeg")

@app.post("/api/video/cancel/{task_id}")
async def cancel_video_task(task_id: str):
    task = video_proc.get_task(task_id)
    if task:
        task.request_cancel()
        return {"success": True, "message": "取消请求已发送"}
    return {"success": False, "message": "任务不存在"}

# WebSocket 实时流管道 (手机摄像头 / 本地摄像头推流)
@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = f"client_{int(time.time()*1000)}"
    active_stream_sources.add(websocket)
    
    last_process_time = time.time()
    fps_count = 0
    current_fps = 0.0

    try:
        while True:
            # 接收客户端二进制帧或控制文本
            data = await websocket.receive()
            if "bytes" in data:
                frame_bytes = data["bytes"]
                nparr = np.frombuffer(frame_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    # 换脸处理
                    if CURRENT_SOURCE_FACE["embedding"] is not None:
                        faces = analyzer.detect_faces(frame)
                        if faces:
                            target_face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
                            frame = swapper.swap_face(
                                frame,
                                target_face,
                                CURRENT_SOURCE_FACE["embedding"],
                                CURRENT_SOURCE_FACE["crop_image"]
                            )

                    fps_count += 1
                    now = time.time()
                    if now - last_process_time >= 1.0:
                        current_fps = round(fps_count / (now - last_process_time), 1)
                        fps_count = 0
                        last_process_time = now

                    # 压成快速 JPEG 回传
                    _, out_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    out_bytes = out_buf.tobytes()
                    
                    # 回传给推流方与屏幕监视端
                    await websocket.send_bytes(out_bytes)
            elif "text" in data:
                msg = json.loads(data["text"])
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "fps": current_fps}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] 异常断开: {e}")
    finally:
        active_stream_sources.discard(websocket)

