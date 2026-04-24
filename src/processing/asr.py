import whisper

from src.config import ASR_MODEL_SIZE, WHISPER_MODEL_DIR

_model = None


def get_asr_model():
    """延迟加载 Whisper ASR 模型（全局缓存，只加载一次）。"""
    global _model
    if _model is None:
        WHISPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        _model = whisper.load_model(ASR_MODEL_SIZE, download_root=str(WHISPER_MODEL_DIR))
    return _model


def transcribe(audio_path: str, language: str = "zh") -> list[dict]:
    """转录音频并返回带时间戳的片段。

    每个片段字典包含：start, end, text。
    """
    model = get_asr_model()
    result = model.transcribe(audio_path, language=language, fp16
    =False)

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
