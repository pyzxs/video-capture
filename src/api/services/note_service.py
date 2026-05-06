"""Note business logic: CRUD, tree building, image upload."""
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.api.schemas import NoteCreate, NoteOut, NoteTreeOut, NoteUpdate
from src.config import get_config
from src.db.models import Note


def _build_tree(items: list[Note], parent_id: int | None = None) -> list[dict]:
    tree = []
    for item in items:
        if item.parent_id == parent_id:
            node = NoteTreeOut.model_validate(item).model_dump()
            node["children"] = _build_tree(items, item.id)
            tree.append(node)
    return tree


def list_notes(
    db: Session,
    tp: str | None = None,
    parent_id: int | None = None,
    q: str | None = None,
) -> dict:
    query = db.query(Note).order_by(Note.updated_at.desc())
    if q:
        query = query.filter(Note.title.contains(q))
    if tp:
        query = query.filter(Note.tp == tp)
    if parent_id is not None:
        if parent_id == 0:
            query = query.filter(Note.parent_id.is_(None))
        else:
            query = query.filter(Note.parent_id == parent_id)
    items = query.all()
    return {"items": [NoteOut.model_validate(i).model_dump(mode="json") for i in items]}


def get_note_tree(db: Session) -> dict:
    items = db.query(Note).order_by(Note.updated_at.desc()).all()
    return {"tree": _build_tree(items)}


def upload_note_image(file) -> dict:
    ext = Path(file.filename).suffix.lower() if file.filename else ".png"
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
        raise fail_response(status_code=400, message="不支持的图片格式")
    filename = f"note_paste_{uuid.uuid4().hex}{ext}"
    note_dir = Path(get_config("material_dir")) / "note_pastes"
    note_dir.mkdir(parents=True, exist_ok=True)
    dest = note_dir / filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"http://127.0.0.1:8090/api/notes/files/{filename}"}


def get_note_image_path(filename: str) -> str:
    path = Path(get_config("material_dir")) / "note_pastes" / filename
    if not path.exists():
        raise fail_response(status_code=404, message="文件不存在")
    return str(path)


def get_note(db: Session, note_id: int) -> dict:
    n = db.query(Note).get(note_id)
    if not n:
        raise fail_response(status_code=404, message="笔记不存在")
    return NoteOut.model_validate(n).model_dump(mode="json")


def create_note(db: Session, data: NoteCreate) -> dict:
    note = Note(
        title=data.title,
        content=data.content,
        parent_id=data.parent_id,
        tp=data.tp,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note).model_dump(mode="json")


def update_note(db: Session, note_id: int, data: NoteUpdate) -> dict:
    n = db.query(Note).get(note_id)
    if not n:
        raise fail_response(status_code=404, message="笔记不存在")
    if n.is_system:
        raise fail_response(status_code=403, message="系统文件夹不允许编辑")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(n, k, v)
    db.commit()
    db.refresh(n)
    return NoteOut.model_validate(n).model_dump(mode="json")


def delete_note(db: Session, note_id: int) -> dict:
    n = db.query(Note).get(note_id)
    if not n:
        raise fail_response(status_code=404, message="笔记不存在")
    if n.is_system:
        raise fail_response(status_code=403, message="系统文件夹不允许删除")
    children = db.query(Note).filter(Note.parent_id == note_id).all()
    for child in children:
        db.delete(child)
    db.delete(n)
    db.commit()
    return {"ok": True}
