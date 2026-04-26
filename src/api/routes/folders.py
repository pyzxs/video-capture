from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.db.models import Folder, GeneratedVideo, Material, Video

router = APIRouter(prefix="/folders", tags=["文件夹管理"])


@router.get("")
def list_folders(
    folder_type: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Folder).order_by(Folder.id.desc())
    if folder_type:
        query = query.filter(Folder.folder_type == folder_type)
    if q:
        query = query.filter(Folder.name.contains(q))
    items = query.all()
    # 附加每个文件夹下的资源数量
    result = []
    for f in items:
        result.append({
            "id": f.id,
            "name": f.name,
            "folder_type": f.folder_type,
            "created_at": f.created_at,
            "video_count": db.query(Video).filter(Video.folder_id == f.id).count(),
            "material_count": db.query(Material).filter(Material.folder_id == f.id).count(),
            "generated_count": db.query(GeneratedVideo).filter(GeneratedVideo.folder_id == f.id).count(),
        })
    return {"items": result}


@router.post("", status_code=201)
def create_folder(name: str, folder_type: str = "video", db: Session = Depends(get_db)):
    folder = Folder(name=name, folder_type=folder_type)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.put("/{folder_id}")
def update_folder(folder_id: int, name: str, db: Session = Depends(get_db)):
    f = db.query(Folder).get(folder_id)
    if not f:
        raise HTTPException(404, "文件夹不存在")
    f.name = name
    db.commit()
    db.refresh(f)
    return f


@router.delete("/{folder_id}")
def delete_folder(folder_id: int, db: Session = Depends(get_db)):
    f = db.query(Folder).get(folder_id)
    if not f:
        raise HTTPException(404, "文件夹不存在")
    # 将关联资源的 folder_id 置空
    db.query(Video).filter(Video.folder_id == folder_id).update({"folder_id": None})
    db.query(Material).filter(Material.folder_id == folder_id).update({"folder_id": None})
    db.query(GeneratedVideo).filter(GeneratedVideo.folder_id == folder_id).update({"folder_id": None})
    db.delete(f)
    db.commit()
    return {"ok": True}


# ── 移动资源到文件夹 ──

@router.put("/{folder_id}/videos/{video_id}")
def move_video(folder_id: int, video_id: int, db: Session = Depends(get_db)):
    f = db.query(Folder).get(folder_id)
    if not f:
        raise HTTPException(404, "文件夹不存在")
    v = db.query(Video).get(video_id)
    if not v:
        raise HTTPException(404, "视频不存在")
    v.folder_id = folder_id
    db.commit()
    return {"ok": True}


@router.put("/{folder_id}/materials/{material_id}")
def move_material(folder_id: int, material_id: int, db: Session = Depends(get_db)):
    f = db.query(Folder).get(folder_id)
    if not f:
        raise HTTPException(404, "文件夹不存在")
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    m.folder_id = folder_id
    db.commit()
    return {"ok": True}


@router.put("/{folder_id}/generated/{gen_id}")
def move_generated(folder_id: int, gen_id: int, db: Session = Depends(get_db)):
    f = db.query(Folder).get(folder_id)
    if not f:
        raise HTTPException(404, "文件夹不存在")
    g = db.query(GeneratedVideo).get(gen_id)
    if not g:
        raise HTTPException(404, "混剪视频不存在")
    g.folder_id = folder_id
    db.commit()
    return {"ok": True}


@router.delete("/{folder_id}/videos/{video_id}")
def remove_video_from_folder(folder_id: int, video_id: int, db: Session = Depends(get_db)):
    v = db.query(Video).get(video_id)
    if not v:
        raise HTTPException(404, "视频不存在")
    v.folder_id = None
    db.commit()
    return {"ok": True}


@router.delete("/{folder_id}/materials/{material_id}")
def remove_material_from_folder(folder_id: int, material_id: int, db: Session = Depends(get_db)):
    m = db.query(Material).get(material_id)
    if not m:
        raise HTTPException(404, "素材不存在")
    m.folder_id = None
    db.commit()
    return {"ok": True}


@router.delete("/{folder_id}/generated/{gen_id}")
def remove_generated_from_folder(folder_id: int, gen_id: int, db: Session = Depends(get_db)):
    g = db.query(GeneratedVideo).get(gen_id)
    if not g:
        raise HTTPException(404, "混剪视频不存在")
    g.folder_id = None
    db.commit()
    return {"ok": True}
