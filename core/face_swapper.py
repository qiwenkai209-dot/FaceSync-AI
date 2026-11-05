import os
import cv2
import numpy as np
from typing import Optional, Tuple
from core.config import INSWAPPER_MODEL_PATH, DEFAULT_PROVIDERS
from core.face_analyzer import DetectedFace, TEMPLATE_128

class FaceSwapper:
    """换脸核心引擎：支持 ONNX Runtime 硬件加速推理与智能羽化融合"""
    
    def __init__(self, feather_radius: int = 15):
        self.feather_radius = feather_radius
        self.providers = DEFAULT_PROVIDERS
        self.swapper_session = None
        self.is_onnx_ready = False
        self.model_matrix = None
        
        self._init_model()
        self._build_standard_mask()

    def _init_model(self):
        try:
            import onnxruntime as ort
            if INSWAPPER_MODEL_PATH.exists():
                opt = ort.SessionOptions()
                opt.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self.swapper_session = ort.InferenceSession(
                    str(INSWAPPER_MODEL_PATH), opt, providers=self.providers
                )
                self.is_onnx_ready = True
                print(f"[FaceSwapper] 成功载入 Inswapper_128 模型，加速提供者: {self.providers}")
            else:
                print("[FaceSwapper] Inswapper 权重待下载，启用自适应融合引擎")
        except Exception as e:
            print(f"[FaceSwapper] ONNX 初始化失败: {e}，启用自适应融合引擎")

    def _build_standard_mask(self):
        """预计算 128x128 椭圆高斯羽化融合蒙版"""
        mask = np.zeros((128, 128), dtype=np.float32)
        # 椭圆中心 64, 64，半轴 50, 58
        cv2.ellipse(mask, (64, 64), (50, 58), 0, 0, 360, 1.0, -1)
        # 高斯滤波消除边界硬切
        ksize = self.feather_radius * 2 + 1
        self.mask_128 = cv2.GaussianBlur(mask, (ksize, ksize), 0)

    def swap_face(
        self,
        frame: np.ndarray,
        target_face: DetectedFace,
        source_embedding: np.ndarray,
        source_crop_image: Optional[np.ndarray] = None,
        blend_ratio: float = 1.0
    ) -> np.ndarray:
        """
        核心换脸接口
        :param frame: 目标当前帧图像 (BGR uint8)
        :param target_face: 目标画面中检测出的人脸对象
        :param source_embedding: 源人脸 512 维特征
        :param source_crop_image: 源人脸备用图像 (在备用模式下用于仿射融合)
        :param blend_ratio: 融合混合比例 0.0 ~ 1.0
        :return: 换脸后的合成图像 (BGR uint8)
        """
        if frame is None or target_face is None or target_face.affine_matrix is None:
            return frame

        h, w = frame.shape[:2]
        m = target_face.affine_matrix

        # 1. 裁剪并对齐目标人脸至 128x128
        target_crop_128 = cv2.warpAffine(
            frame, m, (128, 128), borderMode=cv2.BORDER_REFLECT101
        )

        if self.is_onnx_ready and self.swapper_session:
            swapped_128 = self._infer_inswapper(target_crop_128, source_embedding)
        else:
            swapped_128 = self._blend_fallback(target_crop_128, source_crop_image)

        # 2. 计算逆仿射变换矩阵
        inv_m = cv2.invertAffineTransform(m)

        # 3. 将 128x128 换脸局部图与高斯蒙版映射回原图分辨率
        warped_face = cv2.warpAffine(
            swapped_128, inv_m, (w, h), borderMode=cv2.BORDER_REFLECT101
        )
        warped_mask = cv2.warpAffine(
            self.mask_128, inv_m, (w, h), flags=cv2.INTER_LINEAR
        )
        
        # 4. 蒙版融合
        warped_mask = np.clip(np.expand_dims(warped_mask, axis=-1) * blend_ratio, 0.0, 1.0)
        
        output_frame = (warped_face.astype(np.float32) * warped_mask + 
                        frame.astype(np.float32) * (1.0 - warped_mask))
        return np.clip(output_frame, 0, 255).astype(np.uint8)

    def _infer_inswapper(self, target_crop_128: np.ndarray, source_embedding: np.ndarray) -> np.ndarray:
        """Inswapper ONNX 模型推理执行"""
        # BGR -> RGB
        blob = cv2.cvtColor(target_crop_128, cv2.COLOR_BGR2RGB).astype(np.float32)
        blob = blob / 255.0
        blob = np.transpose(blob, (2, 0, 1))  # (3, 128, 128)
        blob = np.expand_dims(blob, axis=0)   # (1, 3, 128, 128)

        # 规范化 source_embedding 为 (1, 512)
        emb = source_embedding.reshape(1, -1).astype(np.float32)

        inputs = {
            self.swapper_session.get_inputs()[0].name: blob,
            self.swapper_session.get_inputs()[1].name: emb
        }
        pred = self.swapper_session.run(None, inputs)[0][0]
        
        # (3, 128, 128) -> (128, 128, 3)
        pred = np.transpose(pred, (1, 2, 0)) * 255.0
        pred = np.clip(pred, 0, 255).astype(np.uint8)
        return cv2.cvtColor(pred, cv2.COLOR_RGB2BGR)

    def _blend_fallback(self, target_crop_128: np.ndarray, source_crop_image: Optional[np.ndarray]) -> np.ndarray:
        """自适应备用融合器 (无 ONNX 权重时的视觉演示方案)"""
        if source_crop_image is None:
            return target_crop_128
        
        src_resized = cv2.resize(source_crop_image, (128, 128))
        
        # 肤色/亮度直方图色彩自适应匹配
        src_ycr_cb = cv2.cvtColor(src_resized, cv2.COLOR_BGR2YCrCb)
        tgt_ycr_cb = cv2.cvtColor(target_crop_128, cv2.COLOR_BGR2YCrCb)
        
        # 调整亮度通道 Y 的均值与方差
        src_y, src_cr, src_cb = cv2.split(src_ycr_cb)
        tgt_y, tgt_cr, tgt_cb = cv2.split(tgt_ycr_cb)
        
        src_y = np.clip((src_y.astype(np.float32) - np.mean(src_y)) * (np.std(tgt_y) / (np.std(src_y) + 1e-5)) + np.mean(tgt_y), 0, 255).astype(np.uint8)
        src_cr = np.clip((src_cr.astype(np.float32) - np.mean(src_cr)) + np.mean(tgt_cr), 0, 255).astype(np.uint8)
        src_cb = np.clip((src_cb.astype(np.float32) - np.mean(src_cb)) + np.mean(tgt_cb), 0, 255).astype(np.uint8)
        
        matched_src = cv2.cvtColor(cv2.merge([src_y, src_cr, src_cb]), cv2.COLOR_YCrCb2BGR)
        
        # 结合细节叠加
        blended = cv2.addWeighted(matched_src, 0.75, target_crop_128, 0.25, 0)
        return blended

