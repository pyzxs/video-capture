from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from src.db.models import Setting
from starlette.responses import JSONResponse

from src.api.routes import api_router
from src.db.engine import init_db
from src.logger import get_logger


def create_app() -> FastAPI:
    app = FastAPI(title="视频处理工具 API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger = get_logger("error")
        logger.error("捕获异常: %s %s | %s", request.method, request.url.path, exc, exc_info=True)
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": str(exc.detail),
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def log_errors(request: Request, exc: Exception):
        logger = get_logger("error")
        logger.error("捕获异常: %s %s | %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": f"服务器内部错误: {exc}",
                "data": None,
            },
        )

    app.include_router(api_router)

    @app.on_event("startup")
    def startup():
        init_db()
        from src.db.models import Setting
        from src.db.engine import SessionLocal
        db = SessionLocal()
        try:
            # 如果 settings 表为空，从 config.json 导入初始配置
            if db.query(Setting).count() == 0:
                _import_config_to_db(db)
            # 从 DB 同步配置到 config.json（保证 DB 为配置唯一来源）
            from src.config import save_config
            items = db.query(Setting).all()
            data = {s.key: s.value for s in items if s.is_active and s.value}
            save_config(data)
        finally:
            db.close()

        # 确保默认智能体存在
        from src.services.agents import ensure_default_agents
        ensure_default_agents()


def _import_config_to_db(db):
    """将 config.json 中的配置导入到 settings 表（仅在首次启动时调用）。"""
    import json
    from pathlib import Path

    config_path = Path("config.json")
    if not config_path.exists():
        return

    config_data = json.loads(config_path.read_text(encoding="utf-8"))

    # 每个配置项对应的分组和描述
    SETTING_META = {
        "llm_api_key": ("探索大模型", "LLM API密钥",1),
        "llm_base_url": ("探索大模型", "LLM API地址",1),
        "llm_model": ("探索大模型", "LLM 模型名称",1),
        "llm_provider": ("探索大模型", "LLM 供应商",1),
        "asr_model_size": ("语音转文本", "ASR 模型大小",0),
        "asr_api_base_url": ("语音转文本", "ASR API地址",1),
        "asr_api_key": ("语音转文本", "ASR API密钥",1),
        "asr_api_model": ("语音转文本", "ASR 模型名称",1),
        "whisper_model_dir": ("语音转文本", "Whisper 模型目录",0),
        "vector_db_path": ("embedding", "向量数据库路径",0),
        "embedding_model": ("embedding", "Embedding 模型名称",1),
        "embedding_device": ("embedding", "Embedding 运行设备",1),
        "embedding_api_key": ("embedding", "Embedding API密钥",1),
        "embedding_api_base_url": ("embedding", "Embedding API地址",1),
        "tts_api_key": ("文本转语音", "TTS API密钥",1),
        "tts_api_base_url": ("文本转语音", "TTS API地址",1),
        "tts_model": ("文本转语音", "TTS 模型名称",1),
        "tts_voice": ("文本转语音", "TTS 音色",1),
        "source_dir": ("视频存储", "源视频目录",1),
        "material_dir": ("视频存储", "素材目录",1),
        "mixed_dir": ("视频存储", "混剪目录",1),
        "paragraph_gap_threshold": ("剪辑设置", "段落合并时间阈值(秒)"),
        "subtitle_crop_bottom": ("剪辑设置", "字幕底部裁剪像素"),
        "log_level": ("系统设置", "日志级别",0),
        "log_dir": ("系统设置", "日志目录",0),
    }

    for key, value in config_data.items():
        group, description, is_active = SETTING_META.get(key, ("系统设置", "",0))
        db.add(Setting(key=key, value=str(value), group=group, description=description), is_active=is_active)
    db.commit()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
