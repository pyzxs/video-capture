"""Folder business logic: CRUD, resource moving."""
from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.db.models import Folder, GeneratedVideo, Material, Video


def list_folders(db: Session, folder_type: str | None = None, q: str | None = None) -> dict:
    query = db.query(Folder).order_by(Folder.id.desc())
    if folder_type:
        query = query.filter(Folder.folder_type == folder_type)
    if q:
        query = query.filter(Folder.name.contains(q))
    items = query.all()
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


def create_folder(db: Session, name: str, folder_type: str = "video") -> Folder:
    folder = Folder(name=name, folder_type=folder_type)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def update_folder(db: Session, folder_id: int, name: str) -> Folder:
    f = db.query(Folder).get(folder_id)
    if not f:
        raise fail_response(status_code=404, message="文件夹不存在")
    f.name = name
    db.commit()
    db.refresh(f)
    return f


def delete_folder(db: Session, folder_id: int) -> dict:
    f = db.query(Folder).get(folder_id)
    if not f:
        raise fail_response(status_code=404, message="文件夹不存在")
    db.query(Video).filter(Video.folder_id == folder_id).update({"folder_id": None})
    db.query(Material).filter(Material.folder_id == folder_id).update({"folder_id": None})
    db.query(GeneratedVideo).filter(GeneratedVideo.folder_id == folder_id).update({"folder_id": None})
    db.delete(f)
    db.commit()
    return {"ok": True}


def move_video_to_folder(db: Session, folder_id: int, video_id: int) -> dict:
    f = db.query(Folder).get(folder_id)
    if not f:
        raise fail_response(status_code=404, message="文件夹不存在")
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    v.folder_id = folder_id
    db.commit()
    return {"ok": True}


def move_material_to_folder(db: Session, folder_id: int, material_id: int) -> dict:
    f = db.query(Folder).get(folder_id)
    if not f:
        raise fail_response(status_code=404, message="文件夹不存在")
    m = db.query(Material).get(material_id)
    if not m:
        raise fail_response(status_code=404, message="素材不存在")
    m.folder_id = folder_id
    db.commit()
    return {"ok": True}


def move_generated_to_folder(db: Session, folder_id: int, gen_id: int) -> dict:
    f = db.query(Folder).get(folder_id)
    if not f:
        raise fail_response(status_code=404, message="文件夹不存在")
    g = db.query(GeneratedVideo).get(gen_id)
    if not g:
        raise fail_response(status_code=404, message="混剪视频不存在")
    g.folder_id = folder_id
    db.commit()
    return {"ok": True}


def remove_video_from_folder(db: Session, video_id: int) -> dict:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    v.folder_id = None
    db.commit()
    return {"ok": True}


def remove_material_from_folder(db: Session, material_id: int) -> dict:
    m = db.query(Material).get(material_id)
    if not m:
        raise fail_response(status_code=404, message="素材不存在")
    m.folder_id = None
    db.commit()
    return {"ok": True}


def remove_generated_from_folder(db: Session, gen_id: int) -> dict:
    g = db.query(GeneratedVideo).get(gen_id)
    if not g:
        raise fail_response(status_code=404, message="混剪视频不存在")
    g.folder_id = None
    db.commit()
    return {"ok": True}
