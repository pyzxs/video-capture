"""ASR 语音转文本：本地 faster-whisper + CMS 代理双模式。"""
import os

import requests
from faster_whisper import WhisperModel

from src.config import get_config

_model = None


def get_asr_model():
    """延迟加载 Whisper ASR 模型（全局缓存，只加载一次）。

    优先使用本地 CTranslate2 格式模型；首次运行会自动从 HuggingFace
    (Systran/faster-whisper-{size}) 下载，之后离线可用。
    """
    global _model
    if _model is None:
        model_dir = str(get_config("whisper_model_dir").resolve())
        model_size = get_config("asr_model_size")
        for local_only in (True, False):
            try:
                _model = WhisperModel(
                    model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=model_dir,
                    local_files_only=local_only,
                )
                print(f"ASR 模型加载成功: {model_size} (local_only={local_only})")
                break
            except Exception as e:
                if local_only:
                    print(f"本地缓存未命中，尝试从 HuggingFace 下载模型...")
                else:
                    raise RuntimeError(f"ASR 模型下载失败: {e}") from e
    return _model


def transcribe(audio_path: str, language: str = "zh") -> list[dict]:
    """转录音频并返回带时间戳的片段。

    每个片段字典包含：start, end, text。
    """
    print("转录返回: {}".format(audio_path))
    model = get_asr_model()
    print(f"获取模型: {model}")
    segs, info = model.transcribe(audio_path, language=language)
    print(f"检测到的语言: {info.language}, 语言概率: {info.language_probability}")

    segments = []
    for seg in segs:
        text = seg.text.strip()
        if text:
            segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": text,
            })
    return segments


def transcribe_return_text(audio_path: str, language: str = "zh") -> str:
    """直接放回文本内容。

    每个片段字典包含：start, end, text。
    """
    model = get_asr_model()
    print(f"获取模型: {model}")
    segs, info = model.transcribe(audio_path, language=language)
    print(f"检测到的语言: {info.language}, 语言概率: {info.language_probability}")

    segments = []
    for seg in segs:
        text = seg.text.strip()
        if text:
            segments.append(text)
    return "\n".join(segments)


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
