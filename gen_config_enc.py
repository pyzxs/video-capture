"""一次性脚本：生成加密的 config.enc 模板文件，user_id/api_key 为空。"""
import base64
import json

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_SALT = b"video-capture\x00salt\x00v1"
_APP_SECRET = "vc-cfg-enc-v1.0-dont-change-this-publicly"

kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=480_000)
raw = kdf.derive(_APP_SECRET.encode())
key = base64.urlsafe_b64encode(raw)

f = Fernet(key)

data = {
    "llm_model": "deepseek-chat",
    "llm_provider": "deepseek",
    "asr_api_model": "whisper-tiny",
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

# https://video-capture.weigou365.cn
plain = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
encrypted = f.encrypt(plain)

with open("config.enc", "wb") as fh:
    fh.write(encrypted)

print(f"config.enc 已生成，大小: {len(encrypted)} bytes")

# 验证
f2 = Fernet(key)
with open("config.enc", "rb") as fh:
    decrypted = json.loads(f2.decrypt(fh.read()))
assert decrypted["user_id"] == ""
assert decrypted["api_key"] == ""
print("验证通过: user_id 和 api_key 均为空")
