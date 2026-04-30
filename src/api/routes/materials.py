import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.logger import  default_logger as logger
from src.api.deps import get_db
from src.api.schemas import MaterialCreate, MaterialOut, MaterialTtsRequest, MaterialUpdate, PaginatedMaterials
from src.config import get_config
from src.db.vector import VectorStore
from src.db.models import Material
from src.processing.ffmpeg import get_video_duration, get_video_metadata
from src.services.tts import synthesize
from src.utils import ensure_date_dir, get_image_size_imageio, generate_thumbnail, thumb_url

router = APIRouter(prefix="/materials", tags=["素材管理"])

_vector_store: "VectorStore | None" = None


def _get_vector_store():
    global _vector_store
    if _vector_store is None:
        from src.db.vector import VectorStore
        _vector_store = VectorStore()
    return _vector_store


def _detect_type(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    if ext in {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v"}:
        return "video"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
        return "image"
    if ext in {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"}:
        return "audio"
    return "scene"


@router.get("")
def list_materials(
    type: str | None = None,
    q: str | None = None,
    folder_id: int | None = None,
    status: int | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
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
    # Convert thumbnail filepath to URL
    for m in items:
        if m.type == "image" and m.id:
            m.thumbnail = f"/api/materials/{m.id}/file"
        else:
            m.thumbnail = thumb_url(m.thumbnail)
    return {"items": items, "total": total}


@router.get("/{material_id}")
def get_material(material_id: int, db: Session = Depends(get_db)):
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    return m


@router.post("/upload", status_code=201)
def create_material_with_file(
    file: UploadFile | None = None,
    type: str = Form("video"),
    content: str = Form(""),
    start_time: float = Form(0.0),
    end_time: float = Form(0.0),
    frame_width: int = Form(0),
    frame_height: int = Form(0),
    frame_rate: float = Form(0.0),
    filename: str = Form(""),
    status: int = Form(1),
    folder_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    filepath = ""

    if file:
        print(f" {type} {file}")
        ext = Path(file.filename).suffix if file.filename else ".mp4"
        mat_type = type or _detect_type(file.filename or "file.mp4")
        filename = file.filename or f"{uuid.uuid4().hex}{ext}"
        dest = ensure_date_dir(get_config("material_dir"), filename)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        filepath = str(dest)

        if mat_type == "video":
            duration = get_video_duration(filepath)
            meta = get_video_metadata(filepath)
            start_time = start_time or 0.0
            end_time = end_time or duration
            if not frame_width:
                frame_width = meta.get("frame_width", 0)
            if not frame_height:
                frame_height = meta.get("frame_height", 0)
            if not frame_rate:
                frame_rate = meta.get("frame_rate", 0.0)
        elif mat_type == "image":
            frame_width, frame_height = get_image_size_imageio(filepath)
            pass
        elif mat_type == "audio":
            pass  # 图片素材不需要额外提取元数据
        type = mat_type
    else:
        if not content and type not in ("video", "image"):
            raise HTTPException(400, "文本或场景类型必须提供内容")

    print(f" 类型{type}")
    thumb = ""
    if filepath:
        if type in ("video", "scene"):
            thumb = generate_thumbnail(filepath)
        elif type == "image":
            thumb = filepath  # 图片文件本身即可作为缩略图
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

    # 向量化文本内容
    if content:
        try:
            _get_vector_store().add_material(material.id, content, {
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

    return material


@router.post("", status_code=201)
def create_material(
    data: MaterialCreate,
    db: Session = Depends(get_db),
):
    """JSON 方式创建素材（文本/场景等无需上传文件的类型）。"""
    if data.type != "audio" and not data.filepath:
        raise HTTPException(400, "视频/图片类型需通过 /upload 上传文件")

    print(f" 获取data {data.__dict__}")
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
        try:
            _get_vector_store().add_material(material.id, material.content, {
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

    return material


@router.put("/{material_id}", response_model=MaterialOut)
def update_material(material_id: int, data: MaterialUpdate, db: Session = Depends(get_db)):
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)

    # 更新向量数据库
    if m.content:
        try:
            _get_vector_store().add_material(material_id, m.content, {
                "type": m.type,
                "start_time": m.start_time,
                "end_time": m.end_time,
                "frame_width": m.frame_width,
                "frame_height": m.frame_height,
                "frame_rate": m.frame_rate,
                "filename": m.filename or "",
                "filepath": m.filepath or "",
            })
        except Exception:
            pass

    return m


@router.delete("/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    # 删除向量索引
    try:
        _get_vector_store().delete_material(material_id)
    except Exception:
        pass
    # 删除文件
    if m.filepath and Path(m.filepath).exists():
        Path(m.filepath).unlink(missing_ok=True)
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.post("/tts", status_code=201)
def create_material_by_tts(
    data: MaterialTtsRequest,
    db: Session = Depends(get_db),
):
    """将文本合成为语音并创建音频素材。"""
    if not data.text.strip():
        raise HTTPException(400, "请提供文本内容")

    try:
        audio_path = synthesize(text=data.text, voice=data.voice)
    except Exception as e:
        raise HTTPException(500, f"语音合成失败: {e}")

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

    # 向量化文本内容
    try:
        _get_vector_store().add_material(material.id, data.text, {
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

    return material



@router.get("/{material_id}/file")
def get_material_file(material_id: int, db: Session = Depends(get_db)):
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    if not m.filepath or not Path(m.filepath).exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(m.filepath)


@router.post("/from-segment", status_code=201)
def create_material_from_segment(
    source_id: int = Form(...),
    start_frame: float = Form(0),
    end_frame: float = Form(0),
    db: Session = Depends(get_db),
):
    """从已有视频素材裁剪片段，生成新的 status=0 素材。"""
    import subprocess
    from src.processing.ffmpeg import ffmpeg_prefix as ff

    source = db.query(Material).get(source_id)
    if not source or not source.filepath or not Path(source.filepath).exists():
        raise HTTPException(404, "源素材不存在")

    if end_frame <= start_frame:
        raise HTTPException(400, "end_frame 必须大于 start_frame")

    fps = source.frame_rate or 30
    start_sec = start_frame / fps
    dur_sec = (end_frame - start_frame) / fps

    out_dir = ensure_date_dir(get_config("material_dir"))
    out_name = f"seg_{source.id}_{uuid.uuid4().hex[:8]}.mp4"
    out_path = str(Path(out_dir) / out_name)

    cmd = [
        f"{ff}ffmpeg", "-y",
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
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"裁剪失败: {e.stderr[-200:] if e.stderr else ''}")

    if not Path(out_path).exists() or Path(out_path).stat().st_size == 0:
        raise HTTPException(500, "裁剪输出为空")

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
        status=0,  # cached/temp
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
        "frame_width": seg.frame_width,
        "frame_height": seg.frame_height,
        "duration": dur_sec,
        "status": seg.status,
        "thumbnail": thumb_url(seg.thumbnail),
    }
