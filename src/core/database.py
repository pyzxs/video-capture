from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import DATABASE_URL

# 确保数据库目录存在
db_path = DATABASE_URL.replace("sqlite:///", "")
if db_path and db_path != DATABASE_URL:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """创建所有数据库表。"""
    from src.models import models
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
