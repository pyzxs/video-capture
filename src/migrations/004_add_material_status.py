"""为 materials 表添加 status 字段（1=有效, 0=缓存）。"""

from sqlalchemy import text


def run(engine):
    with engine.connect() as conn:
        # 检查列是否已存在
        result = conn.execute(
            text("SELECT COUNT(*) FROM pragma_table_info('materials') WHERE name='status'")
        )
        if result.scalar() == 0:
            conn.execute(text("ALTER TABLE materials ADD COLUMN status INTEGER DEFAULT 1"))
            conn.commit()
