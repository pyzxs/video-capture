"""为 settings 表添加 is_hidden 字段。"""

from sqlalchemy import text


def run(engine):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM pragma_table_info('settings') WHERE name='is_hidden'")
        )
        if result.scalar() == 0:
            conn.execute(text("ALTER TABLE settings ADD COLUMN is_hidden INTEGER DEFAULT 0"))
            conn.commit()
