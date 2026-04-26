from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import NoteCreate, NoteOut, NoteTreeOut, NoteUpdate
from src.db.models import Note

router = APIRouter(prefix="/notes", tags=["笔记管理"])


def _build_tree(items: list[Note], parent_id: int | None = None) -> list[dict]:
    tree = []
    for item in items:
        if item.parent_id == parent_id:
            node = NoteTreeOut.model_validate(item).model_dump()
            node["children"] = _build_tree(items, item.id)
            tree.append(node)
    return tree


@router.get("")
def list_notes(
    tp: str | None = None,
    parent_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
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


@router.get("/tree")
def get_note_tree(db: Session = Depends(get_db)):
    items = db.query(Note).order_by(Note.updated_at.desc()).all()
    return {"tree": _build_tree(items)}


@router.get("/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).get(note_id)
    if not n:
        raise HTTPException(404, "笔记不存在")
    return NoteOut.model_validate(n).model_dump(mode="json")


@router.post("", status_code=201)
def create_note(data: NoteCreate, db: Session = Depends(get_db)):
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


@router.put("/{note_id}")
def update_note(note_id: int, data: NoteUpdate, db: Session = Depends(get_db)):
    n = db.query(Note).get(note_id)
    if not n:
        raise HTTPException(404, "笔记不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(n, k, v)
    db.commit()
    db.refresh(n)
    return NoteOut.model_validate(n).model_dump(mode="json")


@router.delete("/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    n = db.query(Note).get(note_id)
    if not n:
        raise HTTPException(404, "笔记不存在")
    # 删除子节点
    children = db.query(Note).filter(Note.parent_id == note_id).all()
    for child in children:
        db.delete(child)
    db.delete(n)
    db.commit()
    return {"ok": True}
