from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from src.config import BASE_DIR
from src.db.models import Setting
from starlette.responses import JSONResponse

from src.api.routes import api_router
from src.db.engine import init_db
from src.logger import get_logger, default_logger


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
        default_logger.info("启动startup")
        try:
            # 如果 settings 表为空，从 config.enc 导入初始配置
            if db.query(Setting).count() == 0:
                _import_config_to_db(db)
            # 从 DB 同步配置到 config.enc（保证 DB 为配置唯一来源）
            from src.config import save_config, _load
            items = db.query(Setting).all()
            data = {s.key: s.value for s in items if s.is_active and s.value}
            # Preserve auth fields that exist only in config.enc
            current = _load()
            for key in ("user_id", "api_key"):
                if key in current and current[key]:
                    data[key] = current[key]
            save_config(data)

            # 确保默认笔记文件夹存在
            _ensure_default_note_folder(db)
        finally:
            db.close()

        # 确保默认智能体存在
        from src.services.agents import ensure_default_agents
        ensure_default_agents()

        # 自动注册 CMS 用户（首次启动时）
        from src.auth import get_or_register
        get_or_register()

    def _import_config_to_db(db):
        """将 config.enc 中的配置导入到 settings 表（仅在首次启动时调用）。"""
        from src.config import _load

        from pathlib import Path
        if not Path("config.enc").exists() and not Path("config.json").exists():
            default_logger.warning("配置文件不存在，跳过导入")
            return

        config_data = _load()
        default_logger.info(f"读取到 {len(config_data)} 个配置项")

        # 每个配置项对应的分组、描述、是否启用
        # (group, description, is_active, is_hidden)
        SETTING_META = {
            "llm_model": ("探索大模型", "LLM 模型名称", 1, 1),
            "llm_provider": ("探索大模型", "LLM 供应商", 1, 1),
            "asr_model_size": ("语音转文本", "ASR 模型大小", 0, 1),
            "asr_api_model": ("语音转文本", "ASR 模型名称", 1, 1),
            "whisper_model_dir": ("语音转文本", "Whisper 模型目录", 0, 1),
            "vector_db_path": ("embedding", "向量数据库路径", 0, 1),
            "embedding_model": ("embedding", "Embedding 模型名称", 1, 1),
            "tts_model": ("文本转语音", "TTS 模型名称", 1, 1),
            "tts_voice": ("文本转语音", "TTS 音色", 1, 1),
            "source_dir": ("视频存储", "源视频目录", 1, 0),
            "material_dir": ("视频存储", "素材目录", 1, 0),
            "mixed_dir": ("视频存储", "混剪目录", 1, 0),
            "thumbnail_dir": ("视频存储", "缩略图目录", 1, 0),
            "paragraph_gap_threshold": ("剪辑设置", "段落合并时间阈值(秒)", 1, 0),
            "subtitle_crop_bottom": ("剪辑设置", "字幕底部裁剪像素", 1, 0),
            "log_level": ("系统设置", "日志级别", 0, 1),
            "log_dir": ("系统设置", "日志目录", 0, 1),
            "cms_base_url": ("系统设置", "CMS 服务器地址", 1, 1),
            "user_id": ("系统设置", "用户机器码", 0, 1),
            "api_key": ("系统设置", "CMS API密钥", 0, 1),
        }

        for key, value in config_data.items():
            meta = SETTING_META.get(key, ("系统设置", "", 0, 0))
            group, description, is_active, is_hidden = meta if len(meta) == 4 else (*meta, 1, 0)
            db.add(Setting(
                key=key, value=str(value),
                group=group, description=description,
                is_active=is_active, is_hidden=is_hidden,
            ))
        db.commit()
        default_logger.info(f"成功导入 {len(config_data)} 个配置项到 settings 表")

    def _ensure_default_note_folder(db):
        """确保存在系统默认笔记文件夹。"""
        from src.db.models import Note
        existing = db.query(Note).filter(Note.is_system == True, Note.tp == "folder").first()
        if not existing:
            folder = Note(title="默认笔记", tp="folder", is_system=True)
            db.add(folder)
            db.commit()
            default_logger.info("已创建系统默认笔记文件夹")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/thumbnails/{name}")
    def serve_thumbnail(name: str):
        from src.config import get_config
        thumb_path = get_config("thumbnail_dir") / name
        if not thumb_path.exists():
            raise HTTPException(404, "缩略图不存在")
        from starlette.responses import FileResponse
        return FileResponse(thumb_path, media_type="image/jpeg")

    return app


app = create_app()
