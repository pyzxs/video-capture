"""为 videos / materials / generated_videos 表添加 thumbnail 字段。"""

from sqlalchemy import text


def run(engine):
    with engine.connect() as conn:
        for table in ("videos", "materials", "generated_videos"):
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM pragma_table_info('{table}') WHERE name='thumbnail'")
            )
            if result.scalar() == 0:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN thumbnail VARCHAR(1024) DEFAULT ''"))
                conn.commit()
