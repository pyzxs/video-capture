"""Editor business logic: subtitle extraction, directory listing."""
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.config import OUTPUT_DIR
from src.db.models import Material
from src.processing.asr import transcribe
from src.processing.ffmpeg import ffmpeg_prefix


def extract_subtitles(req, db: Session) -> dict:
    if not req.clips:
        raise fail_response(status_code=400, message="No clips provided")

    all_segments = []
    temp_dir = Path(OUTPUT_DIR) / "video-project-asr"
    temp_dir.mkdir(parents=True, exist_ok=True)

    for clip in req.clips:
        material_id = clip.get("material_id")
        if material_id is None:
            continue

        material = db.query(Material).get(material_id)
        if not material or not Path(material.filepath).exists():
            continue

        src_start = clip.get("src_start", 0)
        src_end = clip.get("src_end", 0)
        timeline_start = clip.get("timeline_start", 0)

        if src_end <= src_start:
            continue

        duration = src_end - src_start
        audio_path = str(temp_dir / f"asr_{material_id}_{src_start:.1f}_{src_end:.1f}.wav")

        cmd = [
            f"{ffmpeg_prefix}ffmpeg", "-y",
            "-ss", str(src_start),
            "-t", str(duration),
            "-i", str(material.filepath),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            audio_path,
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            continue

        if not Path(audio_path).exists() or Path(audio_path).stat().st_size == 0:
            continue

        try:
            segments = transcribe(rf"{audio_path}", language=req.language)
            print(segments, audio_path, req)
        except Exception:
            segments = []

        for seg in segments:
            all_segments.append({
                "text": seg["text"],
                "start": timeline_start + seg["start"],
                "end": timeline_start + seg["end"],
            })

        try:
            pass
            # Path(audio_path).unlink(missing_ok=True)
        except Exception:
            pass

    all_segments.sort(key=lambda s: s["start"])
    return {"segments": all_segments}


def list_dir(dir: str) -> dict:
    p = Path(dir)
    if not p.exists() or not p.is_dir():
        raise fail_response(status_code=400, message="文件夹不存在")

    media_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm',
                  '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
                  '.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a'}
    files = []
    try:
        for entry in sorted(p.iterdir(), key=lambda e: e.name.lower()):
            if entry.is_file() and entry.suffix.lower() in media_exts:
                files.append({"name": entry.name, "path": str(entry)})
    except PermissionError:
        raise fail_response(status_code=403, message="无权限访问该文件夹")

    return {"files": files}
