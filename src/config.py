import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 所有下载模型的根目录
MODEL_DIR = Path(os.getenv("MODEL_DIR", "model"))

# 数据库
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database/material.db")

# 向量存储
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "database/chroma_db")

# 嵌入模型（硅基流动 API）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_EMBEDDING_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1") + "/embeddings"

# ASR 模型（Whisper）：tiny, base, small, medium, large
ASR_MODEL_SIZE = os.getenv("ASR_MODEL", "base")
WHISPER_MODEL_DIR = Path(os.getenv("WHISPER_MODEL_DIR", str(MODEL_DIR / "whisper")))

# 处理后的视频输出目录
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "videos/material")).resolve()

# LLM API 密钥（兼容 Anthropic 格式，如 DeepSeek）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# LLM 模型名称
LLM_MODEL = os.getenv("LLM_MODEL", "DeepSeek-V3.2")

# LLM 自定义 API 地址（如 DeepSeek 的 Anthropic 兼容接口）
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")

# 段落合并阈值（秒）
PARAGRAPH_GAP_THRESHOLD = float(os.getenv("PARAGRAPH_GAP_THRESHOLD", "2.0"))

# 字幕区域裁剪（像素），从视频底部裁掉指定高度以去除硬字幕，0 表示不裁剪
SUBTITLE_CROP_BOTTOM = int(os.getenv("SUBTITLE_CROP_BOTTOM", "0"))

# CosyVoice TTS 模型路径（本地模型，使用 API 时不需要）
COSYVOICE_MODEL_DIR = os.getenv("COSYVOICE_MODEL_DIR", str(MODEL_DIR / "CosyVoice-300M"))

# TTS 语音合成（硅基流动 API）
TTS_MODEL = os.getenv("TTS_MODEL", "FunAudioLLM/CosyVoice2-0.5B")
TTS_VOICE = os.getenv("TTS_VOICE", "FunAudioLLM/CosyVoice2-0.5B:anna")
