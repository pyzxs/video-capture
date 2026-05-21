"""ASR 语音转文本：通过 CMS API 调用 Whisper / 云端 ASR 服务。"""
import os

import requests

from src.config import get_config
from src.processing.ffmpeg import compress_audio_for_asr


def transcribe(audio_path: str, language: str = "zh") -> list[dict]:
    """通过 CMS API 转录音频，返回带时间戳的片段列表。

    每个片段字典包含：start, end, text。
    """
    api_model = get_config("asr_api_model")
    result = _call_asr_api(api_model, audio_path, language)
    segments = result.get("segments", [])
    if not segments:
        text = result.get("text", "")
        if text:
            return [{"start": 0, "end": 0, "text": text}]
    return segments


def transcribe_return_text(audio_path: str, language: str = "zh") -> str:
    """通过 CMS API 转录音频，返回纯文本。"""
    api_model = "FunAudioLLM/SenseVoiceSmall"
    result = _call_asr_api(api_model, audio_path, language)
    return result.get("text", "")


def transcribe_by_api(audio_path: str, language: str = "zh") -> str:
    """通过 CMS API 转录音频，返回纯文本（与 transcribe_return_text 相同）。"""
    return transcribe_return_text(audio_path, language)


def _call_asr_api(api_model, audio_path: str, language: str = "zh") -> dict:
    """调用 CMS ASR 接口，返回完整的 API 响应 data 字典。"""
    from src.auth import get_auth_headers

    api_key = get_config("api_key")
    if not api_key:
        print("未注册 CMS 用户，无法使用 ASR API")
        return {}

    cms_url = get_config("cms_base_url")
    if api_model.startswith("whisper-"):
        url = f"{cms_url}/api/proxy/asr/whisper"
    else:
        url = f"{cms_url}/api/proxy/asr/api"

    headers = get_auth_headers()

    # 压缩音频减少上传体积
    upload_path = compress_audio_for_asr(audio_path)

    try:
        with open(upload_path, "rb") as f:
            mime = "audio/mpeg" if upload_path.endswith(".mp3") else "audio/wav"
            files = {
                "file": (os.path.basename(upload_path), f, mime),
            }
            data = {"model": api_model}
            response = requests.post(url, headers=headers, files=files, data=data, timeout=None)

        if response.status_code == 402:
            print("CMS 额度不足，请充值")
            return {}
        response.raise_for_status()
        result = response.json()
        asr_data = result.get("data", {})
        text = asr_data.get("text", "")
        print("转录结果：", text[:100] if text else "(空)")
        return asr_data
    except Exception as e:
        print("ASR API 请求失败：", e)

    return {}
