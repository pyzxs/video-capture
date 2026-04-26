"""Migration 003: drop generated_video_materials, add data column to generated_videos."""

from sqlalchemy import text


def run(engine):
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS generated_video_materials"))
        try:
            conn.execute(text("ALTER TABLE generated_videos ADD COLUMN data TEXT NOT NULL DEFAULT '{}'"))
        except Exception:
            pass  # column may already exist
        conn.commit()
