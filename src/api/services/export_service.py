"""Export business logic: copy files to destination directory."""
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.db.models import GeneratedVideo, Material, Video
from src.logger import default_logger as logger


def export_files(
    db: Session,
    video_ids: list[int],
    material_ids: list[int],
    generated_ids: list[int],
    dest_dir: str,
) -> dict:
    dest = Path(dest_dir)
    if not dest.exists():
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except Exception:
            raise fail_response(status_code=400, message=f"无法创建目标目录: {dest_dir}")
    if not dest.is_dir():
        raise fail_response(status_code=400, message="目标路径不是目录")

    copied = 0
    errors = []

    for vid in video_ids:
        v = db.query(Video).get(vid)
        if not v or not Path(v.filepath).exists():
            errors.append(f"视频 #{vid} 文件不存在")
            continue
        try:
            shutil.copy2(v.filepath, str(dest / Path(v.filepath).name))
            copied += 1
        except Exception as e:
            errors.append(f"视频 #{vid}: {e}")

    for mid in material_ids:
        m = db.query(Material).get(mid)
        if not m or not Path(m.filepath).exists():
            errors.append(f"素材 #{mid} 文件不存在")
            continue
        try:
            shutil.copy2(m.filepath, str(dest / Path(m.filepath).name))
            copied += 1
        except Exception as e:
            errors.append(f"素材 #{mid}: {e}")

    for gid in generated_ids:
        g = db.query(GeneratedVideo).get(gid)
        if not g or not g.output_filepath or not Path(g.output_filepath).exists():
            errors.append(f"混剪 #{gid} 文件不存在")
            continue
        try:
            name = (g.title or f"mashup_{g.id}").replace("/", "_").replace("\\", "_")
            suffix = Path(g.output_filepath).suffix or ".mp4"
            shutil.copy2(g.output_filepath, str(dest / f"{name}{suffix}"))
            copied += 1
        except Exception as e:
            errors.append(f"混剪 #{gid}: {e}")

    return {"ok": True, "copied": copied, "errors": errors}
