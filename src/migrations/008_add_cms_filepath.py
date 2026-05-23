"""为 materials 表添加 cms_filepath 字段，用于存储擦除前的原始文件路径。"""

from sqlalchemy import text


def run(engine):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM pragma_table_info('materials') WHERE name='cms_filepath'")
        )
        if result.scalar() == 0:
            conn.execute(text("ALTER TABLE materials ADD COLUMN cms_filepath VARCHAR(1024) DEFAULT ''"))
            conn.commit()
