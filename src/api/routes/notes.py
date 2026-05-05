from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import NoteCreate, NoteUpdate
from src.api.services.note_service import (
    create_note,
    delete_note,
    get_note,
    get_note_image_path,
    get_note_tree,
    list_notes,
    update_note,
    upload_note_image,
)

router = APIRouter(prefix="/notes", tags=["笔记管理"])


@router.get("")
def _list_notes(
    tp: str | None = None,
    parent_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    return list_notes(db, tp, parent_id, q)


@router.get("/tree")
def _get_note_tree(db: Session = Depends(get_db)):
    return get_note_tree(db)


@router.post("/upload-image")
def _upload_note_image(file: UploadFile):
    return upload_note_image(file)


@router.get("/files/{filename}")
def _get_note_image(filename: str):
    return FileResponse(get_note_image_path(filename))


@router.get("/{note_id}")
def _get_note(note_id: int, db: Session = Depends(get_db)):
    return get_note(db, note_id)


@router.post("", status_code=201)
def _create_note(data: NoteCreate, db: Session = Depends(get_db)):
    return create_note(db, data)


@router.put("/{note_id}")
def _update_note(note_id: int, data: NoteUpdate, db: Session = Depends(get_db)):
    return update_note(db, note_id, data)


@router.delete("/{note_id}")
def _delete_note(note_id: int, db: Session = Depends(get_db)):
    return delete_note(db, note_id)
