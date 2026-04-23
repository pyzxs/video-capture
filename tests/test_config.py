"""测试配置加载。"""

import os
from pathlib import Path


def test_default_model_dir():
    from src.config import MODEL_DIR
    assert str(MODEL_DIR) == "model"


def test_default_asr_model():
    from src.config import ASR_MODEL_SIZE
    assert ASR_MODEL_SIZE == "base"


def test_default_embedding_model():
    from src.config import EMBEDDING_MODEL
    assert EMBEDDING_MODEL == "BAAI/bge-m3"


def test_default_llm_model():
    from src.config import LLM_MODEL
    assert LLM_MODEL == "DeepSeek-V3.2"


def test_default_whisper_model_dir():
    from src.config import WHISPER_MODEL_DIR
    assert str(WHISPER_MODEL_DIR) == str(Path("model/whisper"))


def test_default_cosyvoice_model_dir():
    from src.config import COSYVOICE_MODEL_DIR
    assert Path(COSYVOICE_MODEL_DIR) == Path("model/CosyVoice-300M")


def test_siliconflow_url_default():
    from src.config import SILICONFLOW_EMBEDDING_URL
    assert "api.siliconflow.cn" in SILICONFLOW_EMBEDDING_URL
    assert SILICONFLOW_EMBEDDING_URL.endswith("/embeddings")
