"""所有后端配置从 config.enc 读取（加密存储），修改配置即时生效。"""

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_data_root() -> str:
    """数据目录：开发时用项目根，打包后用 %APPDATA%/Video Capture。"""
    if getattr(sys, 'frozen', False):
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        root = os.path.join(appdata, 'Video Capture')
        os.makedirs(root, exist_ok=True)
        return root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = _get_data_root()
_DATA_ROOT = Path(BASE_DIR)

_CONFIG_PATH = _DATA_ROOT / "config.enc"
_LEGACY_PATH = _DATA_ROOT / "config.json"

# ── 密钥派生 ──
_SALT = b"video-capture\x00salt\x00v1"
_APP_SECRET = "vc-cfg-enc-v1.0-dont-change-this-publicly"


def _derive_key() -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    raw = kdf.derive(_APP_SECRET.encode())
    return base64.urlsafe_b64encode(raw)


def _get_fernet() -> Fernet:
    return Fernet(_derive_key())


# ── 默认值 ──
_DEFAULTS = {
    "llm_model": "deepseek-chat",
    "llm_provider": "deepseek",
    "asr_model_size": "base",
    "asr_api_model": "FunAudioLLM/SenseVoiceSmall",
    "whisper_model_dir": "storage/model/whisper",
    "vector_db_path": "storage/database/chroma_db",
    "embedding_model": "BAAI/bge-m3",
    "tts_model": "FunAudioLLM/CosyVoice2-0.5B",
    "tts_voice": "FunAudioLLM/CosyVoice2-0.5B:anna",
    "source_dir": "storage/videos/source",
    "material_dir": "storage/videos/material",
    "mixed_dir": "storage/videos/mixed",
    "thumbnail_dir": "storage/thumbnails",
    "paragraph_gap_threshold": 2.0,
    "subtitle_crop_bottom": 0,
    "log_level": "INFO",
    "log_dir": "logs",
    "cms_base_url": "https://video-capture.weigou365.cn",
    "user_id": "",
    "api_key": "",
}

# ── JSON key → Python type ──
_TYPE_MAP = {
    "source_dir": Path,
    "material_dir": Path,
    "mixed_dir": Path,
    "whisper_model_dir": Path,
    "vector_db_path": Path,
    "paragraph_gap_threshold": float,
    "thumbnail_dir": Path,
    "subtitle_crop_bottom": int,
    "log_dir": Path,
}

# 数据库连接（硬编码，需要在 DB 初始化前使用）
DATABASE_URL = f"sqlite:///{BASE_DIR}/storage/database/material.db"

print(f"基础路径地址: {BASE_DIR}")

OUTPUT_DIR = Path(BASE_DIR) / "storage" / "output"

_fernet: Fernet | None = None
_fernet_error: bool = False


def _ensure_fernet() -> Fernet | None:
    global _fernet, _fernet_error
    if _fernet is None and not _fernet_error:
        try:
            _fernet = _get_fernet()
        except Exception:
            _fernet_error = True
    return _fernet


def _migrate_legacy() -> dict | None:
    """如果 config.enc 不存在但旧版 config.json 存在，迁移到加密格式。"""
    if not _LEGACY_PATH.exists():
        return None
    try:
        data = json.loads(_LEGACY_PATH.read_text(encoding="utf-8"))
        # 立即保存为加密格式
        f = _ensure_fernet()
        if f is not None:
            plain = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            _CONFIG_PATH.write_bytes(f.encrypt(plain))
        return data
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _load() -> dict:
    if not _CONFIG_PATH.exists():
        # 尝试从旧版 config.json 迁移
        migrated = _migrate_legacy()
        if migrated is not None:
            return {**dict(_DEFAULTS), **migrated}
        return dict(_DEFAULTS)

    raw = _CONFIG_PATH.read_bytes()
    f = _ensure_fernet()
    if f is not None:
        plain = f.decrypt(raw)
        return {**dict(_DEFAULTS), **json.loads(plain.decode("utf-8"))}
    return dict(_DEFAULTS)


def get_config(key: str):
    """获取配置值（每次调用从 config.enc 重新读取）。"""
    val = _load().get(key, _DEFAULTS.get(key))
    typ = _TYPE_MAP.get(key)
    if typ is Path:
        p = Path(str(val))
        if not p.is_absolute():
            p = Path(BASE_DIR) / p
        return p.resolve()
    if typ is float:
        return float(val)
    if typ is int:
        return int(val)
    return val


def reload_config():
    """重新加载 config.enc（写入端调用）。"""
    pass  # get_config 每次重新读取，无需额外操作


def save_config(data: dict):
    """将配置字典加密写入 config.enc（仅写入非空值，保留文件中已有的值）。"""
    current = _load()
    for k, v in data.items():
        if v:
            current[k] = v

    plain = json.dumps(current, ensure_ascii=False, indent=2).encode("utf-8")

    f = _ensure_fernet()
    if f is not None:
        _CONFIG_PATH.write_bytes(f.encrypt(plain))
    else:
        _CONFIG_PATH.write_bytes(plain)
