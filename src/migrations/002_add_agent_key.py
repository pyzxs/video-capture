from sqlalchemy import text


def run(engine):
    """为已有 agents 表添加 key 列（兼容已存在的情况）。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE agents ADD COLUMN key VARCHAR(100) NOT NULL DEFAULT ''"))
            conn.commit()
    except Exception:
        pass  # 列已存在
