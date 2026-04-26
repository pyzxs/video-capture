"""所有后端配置从 config.json 读取，修改配置即时生效。"""

import json
from pathlib import Path
import os

_CONFIG_PATH = Path("config.json")

# ── 默认值 ──
_DEFAULTS = {
    "llm_api_key": "",
    "llm_base_url": "",
    "llm_model": "deepseek-chat",
    "llm_provider": "openai",
    "asr_model_size": "base",
    "asr_api_base_url": "https://api.siliconflow.cn/v1/audio/transcriptions",
    "asr_api_key": "",
    "asr_api_model": "FunAudioLLM/SenseVoiceSmall",
    "whisper_model_dir": "model/whisper",
    "vector_db_path": "database/chroma_db",
    "embedding_model": "BAAI/bge-m3",
    "embedding_device": "cpu",
    "embedding_api_key": "",
    "embedding_api_base_url": "https://api.siliconflow.cn/v1/embeddings",
    "tts_api_key": "",
    "tts_api_base_url": "https://api.siliconflow.cn/v1/audio/speech",
    "tts_model": "FunAudioLLM/CosyVoice2-0.5B",
    "tts_voice": "FunAudioLLM/CosyVoice2-0.5B:anna",
    "source_dir": "videos/source",
    "material_dir": "videos/material",
    "mixed_dir": "videos/mixed",
    "paragraph_gap_threshold": 2.0,
    "subtitle_crop_bottom": 0,
    "log_level": "INFO",
    "log_dir": "logs",
}

# ── JSON key → Python type ──
_TYPE_MAP = {
    "source_dir": Path,
    "material_dir": Path,
    "mixed_dir": Path,
    "whisper_model_dir": Path,
    "paragraph_gap_threshold": float,
    "subtitle_crop_bottom": int,
    "log_dir": str,
}

# 数据库连接（硬编码，需要在 DB 初始化前使用）
DATABASE_URL = "sqlite:///resource/database/material.db"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load() -> dict:
    if _CONFIG_PATH.exists():
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    return dict(_DEFAULTS)


def get_config(key: str):
    """获取配置值（每次调用从 config.json 重新读取）。"""
    val = _load().get(key, _DEFAULTS.get(key))
    typ = _TYPE_MAP.get(key)
    if typ is Path:
        return Path(str(val)).resolve()
    if typ is float:
        return float(val)
    if typ is int:
        return int(val)
    return val


def reload_config():
    """重新加载 config.json（写入端调用）。"""
    pass  # get_config 每次重新读取，无需额外操作


def save_config(data: dict):
    """将配置字典写入 config.json（仅写入非空值，保留文件中已有的值）。"""
    current = _load()
    for k, v in data.items():
        if v:
            current[k] = v
    _CONFIG_PATH.write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
