"""为 videos 表添加 asr_segments / asr_status 字段。"""

from sqlalchemy import text


def run(engine):
    with engine.connect() as conn:
        for col_name, col_def in (
            ("asr_segments", "TEXT"),
            ("asr_status", "VARCHAR(50)"),
        ):
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM pragma_table_info('videos') WHERE name='{col_name}'")
            )
            if result.scalar() == 0:
                conn.execute(text(f"ALTER TABLE videos ADD COLUMN {col_name} {col_def}"))
                conn.commit()
