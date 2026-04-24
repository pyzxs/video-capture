from collections.abc import Generator

from src.core.database import SessionLocal, init_db


def get_db() -> Generator:
    """FastAPI 依赖：提供数据库会话。"""
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
