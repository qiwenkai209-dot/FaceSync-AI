import os
import requests
from tqdm import tqdm
from core.config import MODELS_DIR, MODEL_SOURCES

def download_file(url: str, dest_path: str):
    """带进度条与断点续传的文件下载器"""
    temp_path = dest_path + ".tmp"
    headers = {}
    downloaded_size = 0
    if os.path.exists(temp_path):
        downloaded_size = os.path.getsize(temp_path)
        headers["Range"] = f"bytes={downloaded_size}-"

    print(f"[*] 正在下载: {os.path.basename(dest_path)} (来源: {url})")
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        total_size = int(response.headers.get("content-length", 0)) + downloaded_size
        
        mode = "ab" if downloaded_size > 0 else "wb"
        with open(temp_path, mode) as f, tqdm(
            desc=os.path.basename(dest_path),
            total=total_size,
            initial=downloaded_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))
        
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(temp_path, dest_path)
        print(f"[+] 下载完成: {dest_path}")
        return True
    except Exception as e:
        print(f"[-] 下载失败: {url}, 错误: {e}")
        return False

def ensure_models():
    """检查并自动下载所需模型权重文件"""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    all_success = True
    for model_name, urls in MODEL_SOURCES.items():
        dest = str(MODELS_DIR / model_name)
        if os.path.exists(dest) and os.path.getsize(dest) > 1024 * 1024:
            print(f"[v] 模型已就绪: {model_name}")
            continue
        
        success = False
        for url in urls:
            if download_file(url, dest):
                success = True
                break
        if not success:
            all_success = False
            print(f"[!] 警告: 未能成功下载 {model_name}，系统将以自适应演示模式运行。")
    return all_success

if __name__ == "__main__":
    ensure_models()

