"""ASR 语音转文本：本地 Whisper + CMS 代理双模式。"""
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
    print("转录返回: {}".format(audio_path))
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
    """通过 CMS 代理调用 ASR 大模型语音转文本"""
    from src.auth import get_auth_headers

    api_key = get_config("api_key")
    if not api_key:
        print("未注册 CMS 用户，无法使用 ASR API")
        return ""

    api_model = get_config("asr_api_model")
    cms_url = get_config("cms_base_url")
    url = f"{cms_url}/api/proxy/asr"

    headers = get_auth_headers()

    try:
        with open(audio_path, "rb") as f:
            files = {
                "file": (os.path.basename(audio_path), f, "audio/wav"),
            }
            data = {"model": api_model}
            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)

        if response.status_code == 402:
            print("CMS 额度不足，请充值")
            return ""
        response.raise_for_status()
        result = response.json()
        asr_data = result.get("data", {})
        text = asr_data.get("text", "")
        print("转录结果：", text[:100])
        return text
    except Exception as e:
        print("请求失败：", e)

    return ""
