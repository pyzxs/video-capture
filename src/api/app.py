from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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
        # 从 DB 同步配置到 config.json
        from src.config import save_config
        from src.db.models import Setting
        from src.db.engine import SessionLocal
        db = SessionLocal()
        try:
            items = db.query(Setting).all()
            data = {s.key: s.value for s in items if s.is_active and s.value}
            save_config(data)
        finally:
            db.close()

        # 确保默认智能体存在
        from src.services.agents import ensure_default_agents
        ensure_default_agents()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
