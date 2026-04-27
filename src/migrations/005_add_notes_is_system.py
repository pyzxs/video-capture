"""为 notes 表添加 is_system 字段（标记系统默认文件夹）。"""

from sqlalchemy import text


def run(engine):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM pragma_table_info('notes') WHERE name='is_system'")
        )
        if result.scalar() == 0:
            conn.execute(text("ALTER TABLE notes ADD COLUMN is_system INTEGER DEFAULT 0"))
            conn.commit()
