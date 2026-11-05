let currentFacingMode = "user"; // 'user' 或 'environment'
let mobileStream = null;
let mobileWs = null;
let isStreaming = true;
let isPipVisible = true;
let frameCount = 0;
let lastFpsTime = performance.now();

const videoEl = document.getElementById("mobileVideo");
const pipCanvas = document.getElementById("swappedPipCanvas");
const pipCtx = pipCanvas.getContext("2d");
const wsDot = document.getElementById("wsDot");
const wsStatus = document.getElementById("wsStatus");
const fpsEl = document.getElementById("mobileFps");

const offCanvas = document.createElement("canvas");
const offCtx = offCanvas.getContext("2d");

document.addEventListener("DOMContentLoaded", () => {
  initCamera();
  connectWebSocket();
  requestWakeLock();
});

// 1. 初始化手机摄像头
async function initCamera() {
  if (mobileStream) {
    mobileStream.getTracks().forEach(t => t.stop());
  }

  const constraints = {
    video: {
      facingMode: currentFacingMode,
      width: { ideal: 640 },
      height: { ideal: 480 },
      frameRate: { ideal: 30, max: 30 }
    },
    audio: false
  };

  try {
    mobileStream = await navigator.mediaDevices.getUserMedia(constraints);
    videoEl.srcObject = mobileStream;
    await videoEl.play();
  } catch (err) {
    alert("无法获取手机摄像头权限: " + err.message);
  }
}

// 2. 翻转前置/后置摄像头
function flipCamera() {
  currentFacingMode = currentFacingMode === "user" ? "environment" : "user";
  initCamera();
}

// 3. 建立低延迟 WebSocket 管道
function connectWebSocket() {
  const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProto}//${window.location.host}/ws/stream`;

  mobileWs = new WebSocket(wsUrl);
  mobileWs.binaryType = "arraybuffer";

  mobileWs.onopen = () => {
    wsDot.classList.add("connected");
    wsStatus.innerText = "已连接主机 (实时推流中)";
    startPushLoop();
  };

  // 接收服务端换脸后的实时画面渲染到画中画
  mobileWs.onmessage = (event) => {
    if (typeof event.data !== "string" && isPipVisible) {
      const blob = new Blob([event.data], { type: "image/jpeg" });
      const img = new Image();
      const url = URL.createObjectURL(blob);
      img.onload = () => {
        pipCanvas.width = img.naturalWidth || 240;
        pipCanvas.height = img.naturalHeight || 320;
        pipCtx.drawImage(img, 0, 0, pipCanvas.width, pipCanvas.height);
        URL.revokeObjectURL(url);
      };
      img.src = url;
    }
  };

  mobileWs.onclose = () => {
    wsDot.classList.remove("connected");
    wsStatus.innerText = "连接已断开，3秒后重试...";
    setTimeout(connectWebSocket, 3000);
  };

  mobileWs.onerror = () => {
    mobileWs.close();
  };
}

// 4. 连续抓帧推流循环
function startPushLoop() {
  const push = () => {
    if (!isStreaming) return;

    if (videoEl.readyState >= 2 && mobileWs && mobileWs.readyState === WebSocket.OPEN) {
      offCanvas.width = videoEl.videoWidth || 640;
      offCanvas.height = videoEl.videoHeight || 480;
      offCtx.drawImage(videoEl, 0, 0, offCanvas.width, offCanvas.height);

      offCanvas.toBlob((blob) => {
        if (blob && mobileWs && mobileWs.readyState === WebSocket.OPEN) {
          blob.arrayBuffer().then(buf => mobileWs.send(buf));
          
          frameCount++;
          const now = performance.now();
          if (now - lastFpsTime >= 1000) {
            fpsEl.innerText = (frameCount / ((now - lastFpsTime) / 1000)).toFixed(1);
            frameCount = 0;
            lastFpsTime = now;
          }
        }
      }, "image/jpeg", 0.65); // 0.65 质量比兼顾极佳低延迟与画质
    }

    // 维持约 25~30 FPS
    setTimeout(push, 35);
  };
  push();
}

function toggleStream() {
  isStreaming = !isStreaming;
  const btn = document.getElementById("btnToggleStream");
  if (isStreaming) {
    btn.innerText = "⏹ 停止推流";
    btn.classList.add("active");
    startPushLoop();
  } else {
    btn.innerText = "▶ 恢复推流";
    btn.classList.remove("active");
  }
}

function togglePip() {
  isPipVisible = !isPipVisible;
  pipCanvas.style.display = isPipVisible ? "block" : "none";
}

// 请求常亮，避免手机自动休眠
async function requestWakeLock() {
  try {
    if ("wakeLock" in navigator) {
      await navigator.wakeLock.request("screen");
    }
  } catch (e) {
    // 忽略静默
  }
}

