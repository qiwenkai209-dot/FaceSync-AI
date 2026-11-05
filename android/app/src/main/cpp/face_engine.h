#pragma once

#include <vector>
#include <string>
#include <memory>
#include <opencv2/core.hpp>

namespace facesync {

struct FaceBox {
    float x1, y1, x2, y2;
    float score;
    float kps[10]; // 5个关键点 (x, y) * 5
};

class MobileFaceSwapEngine {
public:
    MobileFaceSwapEngine();
    ~MobileFaceSwapEngine();

    // 初始化模型权重 (Inswapper ONNX/NCNN 与 检测模型)
    bool init(const std::string& model_dir, bool use_vulkan = true);

    // 设置要替换的目标源人脸图像 (提取 512 维特征向量)
    bool setSourceFace(const cv::Mat& source_bgr);

    // 核心实时推流单帧处理 (支持移动端光流跳帧优化)
    cv::Mat processFrame(const cv::Mat& input_bgr, bool force_detect = false);

    // 重置跟踪状态
    void resetTracking();

private:
    class Impl;
    std::unique_ptr<Impl> pimpl;
};

} // namespace facesync

