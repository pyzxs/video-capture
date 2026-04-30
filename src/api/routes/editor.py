"""Editor-specific endpoints: subtitle extraction, etc."""
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.config import OUTPUT_DIR
from src.db.models import Material
from src.processing.asr import transcribe, transcribe_by_api
from src.processing.ffmpeg import ffmpeg_prefix

router = APIRouter(prefix="/editor", tags=["editor"])


class ExtractSubtitlesRequest(BaseModel):
    clips: list[dict]  # [{material_id, src_start, src_end, timeline_start}, ...]
    language: str = "zh"  # ASR language code


@router.post("/extract-subtitles")
def extract_subtitles(req: ExtractSubtitlesRequest, db: Session = Depends(get_db)):
    """Extract subtitles from audio clips via ASR.

    For each audio clip:
    1. Look up the material filepath from DB
    2. Extract the trimmed audio segment via ffmpeg
    3. Run Whisper ASR to get timestamped text segments
    4. Map segment times to absolute timeline positions

    Returns a list of subtitle segments ready for the text track.
    """
    if not req.clips:
        raise HTTPException(400, "No clips provided")

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

        # Extract trimmed audio segment
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
        except subprocess.CalledProcessError as e:
            continue

        if not Path(audio_path).exists() or Path(audio_path).stat().st_size == 0:
            print("文件不存在: {}".format(audio_path))
            continue

        try:
            segments = transcribe(rf"{audio_path}", language=req.language)
        except Exception as e:
            print(e)
            segments = []

        # Map to timeline
        for seg in segments:
            all_segments.append({
                "text": seg["text"],
                "start": timeline_start + seg["start"],
                "end": timeline_start + seg["end"],
            })

        # Cleanup
        try:
            Path(audio_path).unlink(missing_ok=True)
        except Exception:
            pass

    # Merge overlapping/adjacent segments with same text (simple dedup)
    all_segments.sort(key=lambda s: s["start"])

    return {"segments": all_segments}


@router.get("/list-dir")
def list_dir(dir: str):
    """列出文件夹下的媒体文件（视频 + 图片 + 音频）。"""
    import os
    p = Path(dir)
    if not p.exists() or not p.is_dir():
        raise HTTPException(400, "文件夹不存在")

    media_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm',
                  '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
                  '.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a'}
    files = []
    try:
        for entry in sorted(p.iterdir(), key=lambda e: e.name.lower()):
            if entry.is_file() and entry.suffix.lower() in media_exts:
                files.append({"name": entry.name, "path": str(entry)})
    except PermissionError:
        raise HTTPException(403, "无权限访问该文件夹")

    return {"files": files}
