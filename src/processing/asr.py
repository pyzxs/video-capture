import os
from pathlib import Path

import requests
import whisper

from src.config import get_config
from src.logger import default_logger as logger
from src.utils import get_filename_mime

_model = None


def get_asr_model():
    """延迟加载 Whisper ASR 模型（全局缓存，只加载一次）。"""
    global _model
    if _model is None:
        get_config("whisper_model_dir").mkdir(parents=True, exist_ok=True)
        _model = whisper.load_model(get_config("asr_model_size"), download_root=str(get_config("whisper_model_dir")))
    return _model


def transcribe(audio_path: str, language: str = "zh") -> list[dict]:
    """转录音频并返回带时间戳的片段。

    每个片段字典包含：start, end, text。
    """
    model = get_asr_model()
    result = model.transcribe(audio_path, language=language, fp16=False)

    segments = []
    for seg in result["segments"]:
        text = seg["text"].strip()
        if text:
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": text,
            })
    return segments


def transcribe_by_api(audio_path: str, language="zh") -> str:
    """通过ASR大模型语音转文本"""

    api_key = get_config('asr_api_key')
    api_model = get_config("asr_api_model")

    url = get_config("asr_api_base_url")

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    # 使用 files 参数上传文件，model 参数作为表单字段
    files = {
        "file": open(audio_path, "rb"),  # 以二进制方式打开文件
        "model": (None, api_model)  # (filename, value) 传普通字段
    }

    try:
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status()  # 如果状态码不是 2xx，抛出异常
        result = response.json()
        print("转录结果：", result.get("text","")[:100])
        return result.get("text", "")
    except Exception as e:
        print("请求失败：", e)
    finally:
        files["file"].close()  # 确保关闭文件句柄

    return ""
