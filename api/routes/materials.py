from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import MaterialCreate, MaterialOut, MaterialUpdate, PaginatedMaterials
from src.core.vector_store import VectorStore
from src.models.models import Material

router = APIRouter(prefix="/materials", tags=["素材管理"])


@router.get("", response_model=PaginatedMaterials)
def list_materials(
    q: str | None = None,
    type: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(Material).order_by(Material.id.desc())
    if q:
        query = query.filter(Material.content.like(f"%{q}%"))
    if type:
        query = query.filter(Material.type == type)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"items": items, "total": total}


@router.get("/{material_id}", response_model=MaterialOut)
def get_material(material_id: int, db: Session = Depends(get_db)):
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    return m


@router.post("", response_model=MaterialOut, status_code=201)
def create_material(data: MaterialCreate, db: Session = Depends(get_db)):
    m = Material(**data.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)

    # 同步到向量库
    store = VectorStore()
    meta = {
        "type": m.type,
        "start_time": m.start_time,
        "end_time": m.end_time,
        "frame_width": m.frame_width,
        "frame_height": m.frame_height,
        "frame_rate": m.frame_rate,
        "filename": m.filename,
        "filepath": m.filepath,
    }
    store.add_material(m.id, m.content, meta)
    return m


@router.put("/{material_id}", response_model=MaterialOut)
def update_material(material_id: int, data: MaterialUpdate, db: Session = Depends(get_db)):
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)

    # 更新向量库（删除旧向量重新添加）
    store = VectorStore()
    store.delete_material(m.id)
    meta = {
        "type": m.type,
        "start_time": m.start_time,
        "end_time": m.end_time,
        "frame_width": m.frame_width,
        "frame_height": m.frame_height,
        "frame_rate": m.frame_rate,
        "filename": m.filename,
        "filepath": m.filepath,
    }
    store.add_material(m.id, m.content, meta)
    return m


@router.get("/{material_id}/file")
def material_file(material_id: int, db: Session = Depends(get_db)):
    """获取素材视频文件用于播放预览。"""
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    if not m.filepath or not Path(m.filepath).exists():
        raise HTTPException(404, "素材文件不存在")
    return FileResponse(m.filepath, media_type="video/mp4", filename=m.filename)


@router.delete("/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    db.delete(m)
    db.commit()

    # 从向量库删除
    store = VectorStore()
    store.delete_material(material_id)
    return {"ok": True}
