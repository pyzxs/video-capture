import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import PaginatedVideos, VideoOut, VideoSplitOut
from src.config import OUTPUT_DIR, UPLOAD_DIR
from src.core.database import init_db
from src.models.models import Video
from src.pipeline import process_video
from src.processing.paragraph import merge_into_paragraphs
from src.processing.video import get_video_duration, get_video_metadata
from src.video.extract import get_timestamps

router = APIRouter(prefix="/videos", tags=["原始视频管理"])

ALLOWED_EXT = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv"}


@router.get("", response_model=PaginatedVideos)
def list_videos(
    q: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(Video).order_by(Video.id.desc())
    if q:
        query = query.filter(Video.filename.like(f"%{q}%"))
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"items": items, "total": total}


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: int, db: Session = Depends(get_db)):
    v = db.query(Video).get(video_id)
    if not v:
        raise HTTPException(404, "视频不存在")
    return v


@router.post("/upload", response_model=VideoOut, status_code=201)
def upload_video(
    file: UploadFile = File(..., description="视频文件"),
    language: str = "zh",
    db: Session = Depends(get_db),
):
    """上传视频，自动提取元数据（分辨率、帧率）和文案（ASR 语音转文字）。"""
    # 校验文件扩展名
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"不支持的视频格式: {ext}，支持 {ALLOWED_EXT}")

    # 保存上传文件
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / unique_name

    try:
        with save_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(500, f"文件保存失败: {e}")
    finally:
        file.file.close()

    # 提取元数据
    video_path = str(save_path)
    try:
        duration = get_video_duration(video_path)
        meta = get_video_metadata(video_path)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(500, f"视频元数据提取失败: {e}")

    # ASR 语音转文字
    try:
        segments = get_timestamps(video_path, language=language)
        paragraphs = merge_into_paragraphs(segments) if segments else []
        full_text = " ".join(p["text"] for p in paragraphs) if paragraphs else ""
    except Exception as e:
        full_text = ""
        print(f"  ASR 警告: {e}")

    # 存入数据库
    v = Video(
        filename=file.filename or unique_name,
        filepath=video_path,
        duration=duration,
        frame_width=meta["frame_width"],
        frame_height=meta["frame_height"],
        frame_rate=meta["frame_rate"],
        content=full_text,
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    return v


@router.get("/{video_id}/file")
def video_file(video_id: int, db: Session = Depends(get_db)):
    """获取视频文件用于播放/下载。"""
    v = db.query(Video).get(video_id)
    if not v:
        raise HTTPException(404, "视频不存在")
    if not v.filepath or not Path(v.filepath).exists():
        raise HTTPException(404, "视频文件不存在")
    return FileResponse(v.filepath, media_type="video/mp4", filename=v.filename)


@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    v = db.query(Video).get(video_id)
    if not v:
        raise HTTPException(404, "视频不存在")

    # 删除本地文件
    if v.filepath and Path(v.filepath).exists():
        Path(v.filepath).unlink(missing_ok=True)

    db.delete(v)
    db.commit()
    return {"ok": True}


@router.post("/{video_id}/split", response_model=VideoSplitOut)
def split_video(video_id: int, language: str = "zh", db: Session = Depends(get_db)):
    """将原始视频分割为素材片段。"""
    v = db.query(Video).get(video_id)
    if not v:
        raise HTTPException(404, "视频不存在")
    if not os.path.isfile(v.filepath):
        raise HTTPException(400, f"视频文件不存在: {v.filepath}")

    init_db()
    try:
        result = process_video(v.filepath, language=language)
        return VideoSplitOut(material_count=result["material_count"])
    except Exception as e:
        raise HTTPException(500, str(e))
