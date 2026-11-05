// 全局状态
let currentTab = "tabLive";
let activeSourceFace = null;
let liveStreamWs = null;
let isStreaming = false;
let currentLiveSource = "phone"; // "phone" 或 "local"
let localMediaStream = null;
let currentTaskId = null;
let taskPollTimer = null;
let previewPollTimer = null;
let lastWsFrameTime = performance.now();

// 页面载入初始化
document.addEventListener("DOMContentLoaded", () => {
  fetchSystemStatus();
  setupDragAndDrop();
});

// 1. 获取系统硬件与状态
async function fetchSystemStatus() {
  try {
    const res = await fetch("/api/system_status");
    const data = await res.json();

    document.getElementById("hardwareInfo").innerText = `${data.acceleration} (${data.providers[0]})`;
    document.getElementById("lanIpDisplay").innerText = `${data.lan_ip}:${data.port}`;
    
    // 生成移动端二维码
    const mobileUrl = data.mobile_url;
    const mobileLinkEl = document.getElementById("mobileLink");
    mobileLinkEl.href = mobileUrl;
    mobileLinkEl.innerText = mobileUrl;

    const qrContainer = document.getElementById("qrcode");
    qrContainer.innerHTML = "";
    if (window.QRCode) {
      new QRCode(qrContainer, {
        text: mobileUrl,
        width: 140,
        height: 140,
        colorDark: "#0a0e17",
        colorLight: "#ffffff",
        correctLevel: QRCode.CorrectLevel.M
      });
    }

    if (data.current_source && data.current_source.has_face) {
      setFacePreview(data.current_source.crop_path, data.current_source.name);
    }
  } catch (e) {
    console.error("获取系统状态失败:", e);
    document.getElementById("hardwareInfo").innerText = "服务连接异常";
  }
}

// 2. 源人脸上传与拖拽支持
function setupDragAndDrop() {
  const dropBox = document.getElementById("dropAreaFace");
  const fileInput = document.getElementById("faceInput");

  dropBox.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropBox.style.borderColor = "var(--accent-cyan)";
  });

  dropBox.addEventListener("dragleave", () => {
    dropBox.style.borderColor = "var(--border-color)";
  });

  dropBox.addEventListener("drop", (e) => {
    e.preventDefault();
    dropBox.style.borderColor = "var(--border-color)";
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      uploadSourceFace(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length > 0) {
      uploadSourceFace(fileInput.files[0]);
    }
  });
}

async function uploadSourceFace(file) {
  const formData = new FormData();
  formData.append("file", file);

  const statusBadge = document.getElementById("faceStatusBadge");
  statusBadge.innerText = "正在分析人脸...";
  statusBadge.style.color = "#ffb800";

  try {
    const res = await fetch("/api/upload_source_face", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (data.success) {
      setFacePreview(data.crop_url, data.name);
    } else {
      alert("上传失败: " + data.message);
      statusBadge.innerText = "检测失败";
      statusBadge.style.color = "var(--accent-red)";
    }
  } catch (e) {
    alert("网络异常: " + e);
  }
}

function setFacePreview(cropUrl, name) {
  const placeholder = document.getElementById("facePlaceholder");
  const img = document.getElementById("faceImgPreview");
  const nameEl = document.getElementById("sourceFaceName");
  const badge = document.getElementById("faceStatusBadge");

  img.src = cropUrl + "?t=" + Date.now();
  img.style.display = "block";
  placeholder.style.display = "none";
  nameEl.innerText = name || "已就绪";
  badge.innerText = "已提取 512D 特征";
  badge.style.color = "var(--accent-green)";
  activeSourceFace = cropUrl;

  // 激活视频生成按钮 (若已选视频)
  const videoInput = document.getElementById("videoFileInput");
  if (videoInput.files && videoInput.files.length > 0) {
    document.getElementById("btnStartVideoSwap").disabled = false;
  }
}

function resetSourceFace() {
  document.getElementById("facePlaceholder").style.display = "block";
  document.getElementById("faceImgPreview").style.display = "none";
  document.getElementById("faceStatusBadge").innerText = "未就绪";
  document.getElementById("faceStatusBadge").style.color = "var(--text-muted)";
  document.getElementById("sourceFaceName").innerText = "尚未选择";
  document.getElementById("faceInput").value = "";
  activeSourceFace = null;
}

// 3. Tab 标签切换
function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));
  
  event.currentTarget.classList.add("active");
  document.getElementById(tabId).classList.add("active");
}

// 4. 实时摄像头与流式换脸逻辑
function setLiveSource(sourceType) {
  currentLiveSource = sourceType;
  const btnPhone = document.getElementById("btnPhoneSource");
  const btnLocal = document.getElementById("btnLocalSource");

  if (sourceType === "phone") {
    btnPhone.classList.remove("btn-secondary");
    btnPhone.classList.add("btn");
    btnLocal.classList.add("btn-secondary");
    btnLocal.classList.remove("btn");
  } else {
    btnLocal.classList.remove("btn-secondary");
    btnLocal.classList.add("btn");
    btnPhone.classList.add("btn-secondary");
    btnPhone.classList.remove("btn");
  }
}

async function toggleLiveStreaming() {
  if (isStreaming) {
    stopLiveStreaming();
  } else {
    startLiveStreaming();
  }
}

async function startLiveStreaming() {
  const btn = document.getElementById("btnStartLive");
  const dot = document.getElementById("streamDot");
  const statusText = document.getElementById("streamStatusText");
  const canvas = document.getElementById("liveOutputCanvas");
  const ctx = canvas.getContext("2d");

  // 连接 WebSocket
  const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProto}//${window.location.host}/ws/stream`;
  liveStreamWs = new WebSocket(wsUrl);
  liveStreamWs.binaryType = "arraybuffer";

  liveStreamWs.onopen = () => {
    isStreaming = true;
    btn.innerText = "⏹ 停止实时推流";
    btn.classList.add("btn-danger");
    dot.style.background = "var(--accent-green)";
    dot.style.boxShadow = "0 0 8px var(--accent-green)";
    statusText.innerText = currentLiveSource === "phone" ? "正在接收手机推流并换脸..." : "本地摄像头换脸推流中";

    if (currentLiveSource === "local") {
      startLocalCameraCapture();
    }
  };

  // 接收服务端返回的换脸后视频帧
  liveStreamWs.onmessage = (event) => {
    if (typeof event.data === "string") {
      const info = JSON.parse(event.data);
      if (info.type === "pong") {
        document.getElementById("liveFpsDisplay").innerText = info.fps.toFixed(1);
      }
    } else {
      // 二进制图像帧数据
      const blob = new Blob([event.data], { type: "image/jpeg" });
      const img = new Image();
      const url = URL.createObjectURL(blob);
      img.onload = () => {
        canvas.width = img.naturalWidth || 1280;
        canvas.height = img.naturalHeight || 720;
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
      };
      img.src = url;

      // 计算延迟
      const now = performance.now();
      const latency = Math.round(now - lastWsFrameTime);
      lastWsFrameTime = now;
      if (latency > 0 && latency < 500) {
        document.getElementById("liveLatencyDisplay").innerText = `~${latency}ms`;
      }
    }
  };

  liveStreamWs.onclose = () => {
    stopLiveStreaming();
  };

  liveStreamWs.onerror = (e) => {
    console.error("WebSocket 错误:", e);
    stopLiveStreaming();
  };
}

function stopLiveStreaming() {
  isStreaming = false;
  if (liveStreamWs) {
    liveStreamWs.close();
    liveStreamWs = null;
  }
  if (localMediaStream) {
    localMediaStream.getTracks().forEach(t => t.stop());
    localMediaStream = null;
  }

  const btn = document.getElementById("btnStartLive");
  const dot = document.getElementById("streamDot");
  const statusText = document.getElementById("streamStatusText");

  btn.innerText = "▶ 启动实时换脸";
  btn.classList.remove("btn-danger");
  dot.style.background = "#8fa0be";
  dot.style.boxShadow = "none";
  statusText.innerText = "已停止";
  document.getElementById("liveFpsDisplay").innerText = "0.0";
}

// 采集电脑本地摄像头并通过 WebSocket 发送
async function startLocalCameraCapture() {
  try {
    const video = document.getElementById("hiddenLocalVideo");
    localMediaStream = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720 },
      audio: false
    });
    video.srcObject = localMediaStream;
    await video.play();

    const offCanvas = document.createElement("canvas");
    const offCtx = offCanvas.getContext("2d");

    const pushFrame = () => {
      if (!isStreaming || currentLiveSource !== "local") return;

      offCanvas.width = video.videoWidth || 640;
      offCanvas.height = video.videoHeight || 480;
      offCtx.drawImage(video, 0, 0, offCanvas.width, offCanvas.height);

      offCanvas.toBlob((blob) => {
        if (blob && liveStreamWs && liveStreamWs.readyState === WebSocket.OPEN) {
          lastWsFrameTime = performance.now();
          blob.arrayBuffer().then(buf => liveStreamWs.send(buf));
        }
      }, "image/jpeg", 0.7);

      setTimeout(pushFrame, 35); // 约 28 FPS
    };
    pushFrame();
  } catch (err) {
    alert("无法调用电脑本地摄像头: " + err.message);
    stopLiveStreaming();
  }
}

// 5. 视频文件上传、生成与实时逐帧预览
function onVideoFileSelected(input) {
  if (input.files && input.files.length > 0) {
    const file = input.files[0];
    document.getElementById("selectedVideoInfo").style.display = "block";
    document.getElementById("videoFileName").innerText = file.name;
    document.getElementById("videoFileSize").innerText = (file.size / (1024 * 1024)).toFixed(1) + " MB";

    if (activeSourceFace) {
      document.getElementById("btnStartVideoSwap").disabled = false;
    } else {
      alert("提示: 请先在左侧上传一张【源人脸图片】");
    }
  }
}

async function submitVideoSwap() {
  const fileInput = document.getElementById("videoFileInput");
  if (!fileInput.files || fileInput.files.length === 0) {
    alert("请选择视频文件");
    return;
  }
  if (!activeSourceFace) {
    alert("请先上传源人脸图片");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  document.getElementById("btnStartVideoSwap").style.display = "none";
  document.getElementById("btnCancelVideoSwap").style.display = "inline-flex";
  document.getElementById("taskProgressSection").style.display = "block";
  document.getElementById("previewPlaceholder").style.display = "none";
  document.getElementById("videoPreviewLiveImg").style.display = "block";
  document.getElementById("previewBadge").style.display = "inline-block";

  try {
    const res = await fetch("/api/video/start_swap", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (data.success) {
      currentTaskId = data.task_id;
      startPollingTaskStatus(currentTaskId);
    } else {
      alert("任务创建失败: " + data.message);
      resetVideoControls();
    }
  } catch (e) {
    alert("提交视频失败: " + e);
    resetVideoControls();
  }
}

function startPollingTaskStatus(taskId) {
  if (taskPollTimer) clearInterval(taskPollTimer);
  if (previewPollTimer) clearInterval(previewPollTimer);

  // 1. 状态轮询 (每 400ms)
  taskPollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/video/status/${taskId}`);
      const data = await res.json();

      document.getElementById("taskProgressBar").style.width = data.progress + "%";
      document.getElementById("taskProgressPercent").innerText = data.progress.toFixed(1) + "%";
      document.getElementById("taskFramesCount").innerText = `${data.current_frame} / ${data.total_frames}`;
      document.getElementById("taskFpsRate").innerText = data.fps.toFixed(1);
      document.getElementById("taskEta").innerText = data.eta_seconds > 0 ? `${data.eta_seconds} 秒` : "即将完成...";

      if (data.status === "completed") {
        clearInterval(taskPollTimer);
        clearInterval(previewPollTimer);
        onVideoTaskCompleted(data.output_url);
      } else if (data.status === "failed" || data.status === "cancelled") {
        clearInterval(taskPollTimer);
        clearInterval(previewPollTimer);
        alert(data.status === "cancelled" ? "任务已取消" : `处理失败: ${data.error}`);
        resetVideoControls();
      }
    } catch (e) {
      console.error("轮询状态异常:", e);
    }
  }, 400);

  // 2. 实时逐帧画面预览拉取 (每 250ms 拉取最新处理帧)
  const previewImg = document.getElementById("videoPreviewLiveImg");
  previewPollTimer = setInterval(() => {
    previewImg.src = `/api/video/preview/${taskId}?t=` + Date.now();
  }, 250);
}

function onVideoTaskCompleted(outputUrl) {
  resetVideoControls();
  document.getElementById("taskStatusLabel").innerText = "🎉 视频换脸生成成功！已保留原声";
  document.getElementById("taskProgressBar").style.width = "100%";
  document.getElementById("taskProgressPercent").innerText = "100.0%";

  // 激活右侧成品播放器
  const videoEl = document.getElementById("finalResultVideo");
  const placeholder = document.getElementById("resultPlaceholder");
  const downloadBtn = document.getElementById("btnDownloadVideo");

  placeholder.style.display = "none";
  videoEl.style.display = "block";
  videoEl.src = outputUrl;
  videoEl.load();
  videoEl.play();

  downloadBtn.style.display = "inline-block";
  downloadBtn.href = outputUrl;
}

async function cancelVideoTask() {
  if (currentTaskId) {
    await fetch(`/api/video/cancel/${currentTaskId}`, { method: "POST" });
  }
  resetVideoControls();
}

function resetVideoControls() {
  document.getElementById("btnStartVideoSwap").style.display = "inline-flex";
  document.getElementById("btnCancelVideoSwap").style.display = "none";
  if (taskPollTimer) clearInterval(taskPollTimer);
  if (previewPollTimer) clearInterval(previewPollTimer);
}

// 全屏控制
function toggleFullScreen(elemId) {
  const el = document.getElementById(elemId);
  if (!document.fullscreenElement) {
    el.requestFullscreen().catch(err => alert("无法进入全屏: " + err.message));
  } else {
    document.exitFullscreen();
  }
}

