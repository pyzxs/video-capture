"""从 CMS 下载并解压 bin 工具和 Whisper 模型（后台线程 + 进度追踪）。"""
import io
import os
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import requests

from src.config import get_config, BASE_DIR
from src.logger import get_logger

logger = get_logger("model_download")

_BIN_FILES = ["ffmpeg.exe", "ffplay.exe", "ffprobe.exe", "you-get.exe", "yt-dlp.exe"]

_download_lock = threading.Lock()
_download_state = {
    "downloading": False,
    "progress": 0,
    "total": 0,
    "error": None,
}


def get_download_state() -> dict:
    with _download_lock:
        return dict(_download_state)


def resources_ready() -> bool:
    """检查 bin 工具和模型是否都已就绪。"""
    base = Path(BASE_DIR)
    for name in _BIN_FILES:
        if not (base / "bin" / name).exists():
            return False
    model_marker = get_config("whisper_model_dir") / "models--Systran--faster-whisper-base"
    if not model_marker.exists() or not any(model_marker.rglob("*")):
        return False
    return True


def start_download():
    """在后台线程中开始下载资源。重复调用无副作用。"""
    with _download_lock:
        if _download_state["downloading"]:
            return
        _download_state["downloading"] = True
        _download_state["progress"] = 0
        _download_state["total"] = 0
        _download_state["error"] = None

    thread = threading.Thread(target=_do_download, daemon=True)
    thread.start()


def _do_download():
    api_key = get_config("api_key")
    cms_url = get_config("cms_base_url")
    url = f"{cms_url}/api/proxy/resources/download"
    headers = {"X-Api-Key": api_key}

    logger.info("开始从 CMS 下载资源: %s", url)

    try:
        resp = requests.get(url, headers=headers, timeout=1200, stream=True)
        if resp.status_code == 404:
            _set_error("CMS 上资源文件不存在")
            return
        resp.raise_for_status()

        total = int(resp.headers.get("Content-Length", 0))
        with _download_lock:
            _download_state["total"] = total

        # 流式写入临时文件
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        try:
            downloaded = 0
            last_log_pct = -1
            for chunk in resp.iter_content(chunk_size=65536):
                tmp.write(chunk)
                downloaded += len(chunk)
                pct = downloaded * 100 // total if total > 0 else 0
                if pct != last_log_pct:
                    last_log_pct = pct
                    with _download_lock:
                        _download_state["progress"] = downloaded
                    if pct % 10 == 0:
                        logger.info("下载进度: %d%% (%d / %d MB)", pct, downloaded // 1048576, total // 1048576)
            tmp.close()

            logger.info("下载完成，开始解压...")
            with _download_lock:
                _download_state["progress"] = total

            with zipfile.ZipFile(tmp.name, "r") as zf:
                zf.extractall(BASE_DIR)

            logger.info("资源解压完成")
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    except requests.RequestException as e:
        _set_error(f"下载失败: {e}")
        return
    except zipfile.BadZipFile as e:
        _set_error(f"解压失败: {e}")
        return

    with _download_lock:
        _download_state["downloading"] = False


def _set_error(msg: str):
    logger.error(msg)
    with _download_lock:
        _download_state["error"] = msg
        _download_state["downloading"] = False
