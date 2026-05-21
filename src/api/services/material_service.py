"""Material business logic: CRUD, upload, TTS creation, segment creation, vector indexing."""
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.api.schemas import MaterialCreate, MaterialOut, MaterialTtsRequest
from src.config import API_BASE_URL, get_config
from src.db.models import Material
from src.processing.ffmpeg import get_video_info
from src.services.tts import synthesize
from src.utils import ensure_date_dir, get_image_size, generate_thumbnail, thumb_url

_CREATIONFLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

_vector_store: "VectorStore | None" = None


def _get_vector_store():
    global _vector_store
    if _vector_store is None:
        from src.db.vector import VectorStore
        _vector_store = VectorStore()
    return _vector_store


def _index_material_content(material_id: int, content: str, material: Material):
    """Index material content into vector store for semantic search."""
    try:
        _get_vector_store().add_material(material_id, content, {
            "type": material.type,
            "start_time": material.start_time,
            "end_time": material.end_time,
            "frame_width": material.frame_width,
            "frame_height": material.frame_height,
            "frame_rate": material.frame_rate,
            "filename": material.filename or "",
            "filepath": material.filepath or "",
        })
    except Exception:
        pass


def _detect_type(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    if ext in {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v"}:
        return "video"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
        return "image"
    if ext in {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"}:
        return "audio"
    return "scene"


def list_materials(
    db: Session,
    type: str | None = None,
    q: str | None = None,
    folder_id: int | None = None,
    status: int | None = None,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    query = db.query(Material).order_by(Material.id.desc())
    if type:
        query = query.filter(Material.type == type)
    if q:
        query = query.filter(Material.content.contains(q))
    if status is not None:
        query = query.filter(Material.status == status)
    if folder_id is not None:
        if folder_id == 0:
            query = query.filter(Material.folder_id.is_(None))
        else:
            query = query.filter(Material.folder_id == folder_id)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    for m in items:
        if m.id:
            m.file_url = f"{API_BASE_URL}/api/materials/{m.id}/file"
        if m.type == "image" and m.id:
            m.thumbnail = m.file_url  # 图片素材：缩略图即原文件
        else:
            m.thumbnail = thumb_url(m.thumbnail)
    return {"items": items, "total": total}


def get_material(db: Session, material_id: int) -> Material:
    m = db.query(Material).get(material_id)
    if not m:
        raise fail_response(status_code=404, message="素材不存在")
    m.file_url = f"{API_BASE_URL}/api/materials/{m.id}/file"
    if m.type == "image":
        m.thumbnail = m.file_url
    else:
        m.thumbnail = thumb_url(m.thumbnail)
    return m


def create_material_with_file(
    db: Session,
    file,
    type: str = "video",
    content: str = "",
    start_time: float = 0.0,
    end_time: float = 0.0,
    frame_width: int = 0,
    frame_height: int = 0,
    frame_rate: float = 0.0,
    filename: str = "",
    status: int = 1,
    folder_id: int | None = None,
) -> Material:
    filepath = ""

    if file:
        ext = Path(file.filename).suffix if file.filename else ".mp4"
        mat_type = type or _detect_type(file.filename or "file.mp4")
        filename = file.filename or f"{uuid.uuid4().hex}{ext}"
        dest = ensure_date_dir(get_config("material_dir"), filename)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        filepath = str(dest)

        # 如果选择了"音频"类型但上传的是视频文件，提取音频并转为 MP3
        if mat_type == "audio" and _detect_type(filename) == "video":
            from src.processing.ffmpeg import FFMPEG
            audio_dest = dest.with_suffix(".mp3")
            _CREATIONFLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.run(
                [FFMPEG, "-i", str(dest), "-vn", "-c:a", "libmp3lame", "-q:a", "2", "-y", str(audio_dest)],
                check=True, capture_output=True,
                creationflags=_CREATIONFLAGS,
            )
            dest.unlink(missing_ok=True)
            filepath = str(audio_dest)
            filename = audio_dest.name
            ext = ".mp3"

        if mat_type == "video":
            meta = get_video_info(filepath)
            duration = meta["duration"]
            start_time = start_time or 0.0
            end_time = end_time or duration
            if not frame_width:
                frame_width = meta.get("frame_width", 0)
            if not frame_height:
                frame_height = meta.get("frame_height", 0)
            if not frame_rate:
                frame_rate = meta.get("frame_rate", 0.0)
        elif mat_type == "image":
            frame_width, frame_height = get_image_size(filepath)
        type = mat_type
    else:
        if not content and type not in ("video", "image"):
            raise fail_response(status_code=400, message="文本或场景类型必须提供内容")

    thumb = ""
    if filepath:
        if type in ("video", "scene"):
            thumb = generate_thumbnail(filepath)
        elif type == "image":
            thumb = filepath

    material = Material(
        type=type,
        content=content,
        start_time=start_time,
        end_time=end_time,
        frame_width=frame_width,
        frame_height=frame_height,
        frame_rate=frame_rate,
        filename=filename,
        filepath=filepath,
        thumbnail=thumb,
        status=status,
        folder_id=folder_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    if content:
        _index_material_content(material.id, content, material)

    material.file_url = f"{API_BASE_URL}/api/materials/{material.id}/file"
    if material.type == "image":
        material.thumbnail = material.file_url
    else:
        material.thumbnail = thumb_url(material.thumbnail)
    return material


def create_material_json(db: Session, data: MaterialCreate) -> Material:
    if data.type != "audio" and not data.filepath:
        raise fail_response(status_code=400, message="视频/图片类型需通过 /upload 上传文件")

    material = Material(
        type=data.type,
        content=data.content or "",
        start_time=data.start_time or 0.0,
        end_time=data.end_time or 0.0,
        frame_width=data.frame_width or 0,
        frame_height=data.frame_height or 0,
        frame_rate=data.frame_rate or 0.0,
        filename=data.filename or "",
        filepath=data.filepath or "",
        status=data.status,
        folder_id=data.folder_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    if material.content:
        _index_material_content(material.id, material.content, material)

    material.file_url = f"{API_BASE_URL}/api/materials/{material.id}/file"
    if material.type == "image":
        material.thumbnail = material.file_url
    else:
        material.thumbnail = thumb_url(material.thumbnail)
    return material


def update_material(db: Session, material_id: int, data: dict) -> Material:
    m = db.query(Material).get(material_id)
    if not m:
        raise fail_response(status_code=404, message="素材不存在")
    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)

    if m.content:
        _index_material_content(material_id, m.content, m)

    m.file_url = f"{API_BASE_URL}/api/materials/{m.id}/file"
    if m.type == "image":
        m.thumbnail = m.file_url
    else:
        m.thumbnail = thumb_url(m.thumbnail)
    return m


def delete_material(db: Session, material_id: int) -> dict:
    m = db.query(Material).get(material_id)
    if not m:
        raise fail_response(status_code=404, message="素材不存在")
    try:
        _get_vector_store().delete_material(material_id)
    except Exception:
        pass
    if m.filepath and Path(m.filepath).exists():
        Path(m.filepath).unlink(missing_ok=True)
    db.delete(m)
    db.commit()
    return {"ok": True}


def create_material_by_tts(db: Session, data: MaterialTtsRequest) -> Material:
    if not data.text.strip():
        raise fail_response(status_code=400, message="请提供文本内容")

    try:
        audio_path = synthesize(text=data.text, voice=data.voice)
    except Exception as e:
        raise fail_response(status_code=500, message=f"语音合成失败: {e}")

    audio_filename = Path(audio_path).name
    material = Material(
        type="audio",
        content=data.text,
        filename=audio_filename,
        filepath=audio_path,
        status=1,
        folder_id=data.folder_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    if data.text:
        _index_material_content(material.id, data.text, material)

    material.file_url = f"{API_BASE_URL}/api/materials/{material.id}/file"
    material.thumbnail = thumb_url(material.thumbnail)
    return material


def get_material_file_path(db: Session, material_id: int) -> str:
    m = db.query(Material).get(material_id)
    if not m:
        raise fail_response(status_code=404, message="素材不存在")
    if not m.filepath or not Path(m.filepath).exists():
        raise fail_response(status_code=404, message="文件不存在")
    return m.filepath


def create_material_from_segment(
    db: Session,
    source_id: int,
    start_frame: float = 0,
    end_frame: float = 0,
) -> dict:
    import subprocess
    from src.processing.ffmpeg import FFMPEG

    source = db.query(Material).get(source_id)
    if not source or not source.filepath or not Path(source.filepath).exists():
        raise fail_response(status_code=404, message="源素材不存在")

    if end_frame <= start_frame:
        raise fail_response(status_code=400, message="end_frame 必须大于 start_frame")

    fps = source.frame_rate or 30
    start_sec = start_frame / fps
    dur_sec = (end_frame - start_frame) / fps

    out_dir = ensure_date_dir(get_config("material_dir"))
    out_name = f"seg_{source.id}_{uuid.uuid4().hex[:8]}.mp4"
    out_path = str(Path(out_dir) / out_name)

    cmd = [
        FFMPEG, "-y",
        "-ss", f"{start_sec:.3f}",
        "-i", str(source.filepath),
        "-t", f"{dur_sec:.3f}",
        "-c:v", "libx264", "-crf", "18",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-avoid_negative_ts", "make_zero",
        out_path,
    ]
    try:
        subprocess.run(cmd, creationflags=_CREATIONFLAGS, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise fail_response(status_code=500, message=f"裁剪失败: {e.stderr[-200:] if e.stderr else ''}")

    if not Path(out_path).exists() or Path(out_path).stat().st_size == 0:
        raise fail_response(status_code=500, message="裁剪输出为空")

    thumb = generate_thumbnail(out_path)

    seg = Material(
        type="video",
        content=f"{source.content or source.filename} [{start_frame:.0f}-{end_frame:.0f}]",
        filename=out_name,
        filepath=out_path,
        start_time=0.0,
        end_time=dur_sec,
        frame_width=source.frame_width,
        frame_height=source.frame_height,
        frame_rate=fps,
        thumbnail=thumb,
        status=0,
        folder_id=source.folder_id,
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)

    return {
        "id": seg.id,
        "type": seg.type,
        "content": seg.content,
        "filename": seg.filename,
        "filepath": seg.filepath,
        "file_url": f"{API_BASE_URL}/api/materials/{seg.id}/file",
        "frame_width": seg.frame_width,
        "frame_height": seg.frame_height,
        "duration": dur_sec,
        "status": seg.status,
        "thumbnail": thumb_url(seg.thumbnail),
    }
