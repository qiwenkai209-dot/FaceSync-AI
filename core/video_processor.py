import os
import time
import subprocess
import threading
import cv2
import numpy as np
from typing import Optional, Callable
from pathlib import Path
from core.config import FFMPEG_PATH, OUTPUTS_DIR
from core.face_analyzer import FaceAnalyzer, DetectedFace
from core.face_swapper import FaceSwapper

class VideoSwapTask:
    """单个视频换脸任务的生命周期与状态管理"""
    def __init__(self, task_id: str, video_path: str, source_face_data: dict):
        self.task_id = task_id
        self.video_path = video_path
        self.source_face_data = source_face_data
        
        # 任务运行状态
        self.status = "pending"  # pending, processing, completed, failed, cancelled
        self.progress = 0.0      # 0.0 ~ 100.0
        self.current_frame = 0
        self.total_frames = 0
        self.fps = 0.0
        self.eta_seconds = 0
        self.error_message = ""
        self.output_video_path = ""
        self.latest_preview_frame_jpeg: Optional[bytes] = None
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

class VideoProcessor:
    """离线视频换脸生成引擎（支持实时预览与音频保留封装）"""

    def __init__(self, analyzer: FaceAnalyzer, swapper: FaceSwapper):
        self.analyzer = analyzer
        self.swapper = swapper
        self.tasks = {}
        self.lock = threading.Lock()

    def create_task(self, video_path: str, source_face_data: dict) -> VideoSwapTask:
        task_id = f"task_{int(time.time() * 1000)}"
        task = VideoSwapTask(task_id, video_path, source_face_data)
        with self.lock:
            self.tasks[task_id] = task
        return task

    def start_task_async(self, task: VideoSwapTask):
        thread = threading.Thread(target=self._process_video, args=(task,), daemon=True)
        thread.start()

    def get_task(self, task_id: str) -> Optional[VideoSwapTask]:
        with self.lock:
            return self.tasks.get(task_id)

    def _process_video(self, task: VideoSwapTask):
        task.status = "processing"
        start_time = time.time()
        
        cap = cv2.VideoCapture(task.video_path)
        if not cap.isOpened():
            task.status = "failed"
            task.error_message = "无法打开源视频文件"
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        task.total_frames = total_frames

        # 临时中间文件
        temp_no_audio = str(OUTPUTS_DIR / f"{task.task_id}_temp.mp4")
        final_output = str(OUTPUTS_DIR / f"{task.task_id}_swapped.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(temp_no_audio, fourcc, orig_fps, (width, height))

        source_emb = task.source_face_data.get("embedding")
        source_crop = task.source_face_data.get("crop")

        frame_idx = 0
        fps_tracker_time = time.time()
        fps_tracker_frames = 0

        try:
            while cap.isOpened():
                if task._cancel_requested:
                    task.status = "cancelled"
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                frame_idx += 1
                fps_tracker_frames += 1

                # 人脸检测与换脸
                faces = self.analyzer.detect_faces(frame)
                if faces and source_emb is not None:
                    # 默认选择置信度最高或面积最大的人脸
                    target_face = max(faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
                    frame = self.swapper.swap_face(
                        frame, target_face, source_emb, source_crop
                    )

                out_writer.write(frame)

                # 更新实时预览帧 (每2帧生成一次 JPEG 降低开销)
                if frame_idx % 2 == 0 or frame_idx == 1:
                    preview_resized = cv2.resize(frame, (640, int(640 * height / width)))
                    _, buf = cv2.imencode('.jpg', preview_resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    task.latest_preview_frame_jpeg = buf.tobytes()

                # 更新进度与速率
                now = time.time()
                elapsed = now - fps_tracker_time
                if elapsed >= 0.5:
                    current_fps = fps_tracker_frames / elapsed
                    task.fps = round(current_fps, 1)
                    rem_frames = max(0, total_frames - frame_idx)
                    task.eta_seconds = int(rem_frames / current_fps) if current_fps > 0 else 0
                    fps_tracker_time = now
                    fps_tracker_frames = 0

                task.current_frame = frame_idx
                task.progress = round((frame_idx / max(1, total_frames)) * 100.0, 1)

            cap.release()
            out_writer.release()

            if task.status != "cancelled":
                # 合并音频与重新编码为现代浏览器通用的 H.264
                self._remux_audio_and_encode(task.video_path, temp_no_audio, final_output)
                task.output_video_path = f"/outputs/{Path(final_output).name}"
                task.status = "completed"
                task.progress = 100.0
                
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            print(f"[VideoProcessor] 任务处理异常: {e}")
        finally:
            cap.release()
            out_writer.release()
            if os.path.exists(temp_no_audio):
                try:
                    os.remove(temp_no_audio)
                except Exception:
                    pass

    def _remux_audio_and_encode(self, original_video: str, temp_video: str, output_video: str):
        """利用 FFmpeg 无损合并音频并封装成跨平台兼容的 H.264/AAC MP4"""
        temp_audio = f"{temp_video}.aac"
        has_audio = False
        
        # 1. 尝试提取音频
        cmd_extract = [
            FFMPEG_PATH, "-y", "-i", original_video,
            "-vn", "-acodec", "copy", temp_audio
        ]
        try:
            res = subprocess.run(cmd_extract, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0 and os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 100:
                has_audio = True
        except Exception:
            has_audio = False

        # 2. 压制与混流
        if has_audio:
            cmd_mux = [
                FFMPEG_PATH, "-y",
                "-i", temp_video,
                "-i", temp_audio,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-shortest",
                output_video
            ]
        else:
            cmd_mux = [
                FFMPEG_PATH, "-y",
                "-i", temp_video,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                output_video
            ]

        try:
            subprocess.run(cmd_mux, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except Exception as e:
            # 若 libx264 缺失则直接重命名为目标文件
            print(f"[FFmpeg] 封装重转警告: {e}，使用直接输出")
            if os.path.exists(output_video):
                os.remove(output_video)
            os.rename(temp_video, output_video)
        finally:
            if os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass

