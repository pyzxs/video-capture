from sqlalchemy import text


def run(engine):
    """为已有 folders 表添加 folder_type 列（兼容已存在的情况）。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE folders ADD COLUMN folder_type VARCHAR(50) NOT NULL DEFAULT 'video'"))
            conn.commit()
    except Exception:
        pass  # 列已存在
