from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import DATABASE_URL

# 确保数据库目录存在
db_path = DATABASE_URL.replace("sqlite:///", "")
if db_path and db_path != DATABASE_URL:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=30,
    pool_timeout=60,
    connect_args={"check_same_thread": False},
)


# 每个连接建立时自动设置 SQLite 优化参数
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.fetchone()  # 消费返回结果
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, autocommit=False,
                            autoflush=False, )


def init_db():
    """创建所有数据库表。"""
    from src.db import models
    Base.metadata.create_all(engine)
    from src.migrations import _run_all
    _run_all(engine)



def get_session():
    return  SessionLocal()
