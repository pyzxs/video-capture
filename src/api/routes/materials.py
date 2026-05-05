from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import MaterialCreate, MaterialOut, MaterialTtsRequest, MaterialUpdate
from src.api.services.material_service import (
    create_material_by_tts,
    create_material_from_segment,
    create_material_json,
    create_material_with_file,
    delete_material,
    get_material,
    get_material_file_path,
    list_materials,
    update_material,
)

router = APIRouter(prefix="/materials", tags=["素材管理"])


@router.get("")
def _list_materials(
    type: str | None = None,
    q: str | None = None,
    folder_id: int | None = None,
    status: int | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return list_materials(db, type, q, folder_id, status, skip, limit)


@router.get("/{material_id}")
def _get_material(material_id: int, db: Session = Depends(get_db)):
    return get_material(db, material_id)


@router.post("/upload", status_code=201)
def _create_material_with_file(
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
    return create_material_with_file(
        db, file, type, content, start_time, end_time,
        frame_width, frame_height, frame_rate, filename, status, folder_id,
    )


@router.post("", status_code=201)
def _create_material(data: MaterialCreate, db: Session = Depends(get_db)):
    return create_material_json(db, data)


@router.put("/{material_id}", response_model=MaterialOut)
def _update_material(material_id: int, data: MaterialUpdate, db: Session = Depends(get_db)):
    return update_material(db, material_id, data.model_dump(exclude_unset=True))


@router.delete("/{material_id}")
def _delete_material(material_id: int, db: Session = Depends(get_db)):
    return delete_material(db, material_id)


@router.post("/tts", status_code=201)
def _create_material_by_tts(data: MaterialTtsRequest, db: Session = Depends(get_db)):
    return create_material_by_tts(db, data)


@router.get("/{material_id}/file")
def _get_material_file(material_id: int, db: Session = Depends(get_db)):
    return FileResponse(get_material_file_path(db, material_id))


@router.post("/from-segment", status_code=201)
def _create_material_from_segment(
    source_id: int = Form(...),
    start_frame: float = Form(0),
    end_frame: float = Form(0),
    db: Session = Depends(get_db),
):
    return create_material_from_segment(db, source_id, start_frame, end_frame)
