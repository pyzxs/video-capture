from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.services.folder_service import (
    create_folder,
    delete_folder,
    list_folders,
    move_generated_to_folder,
    move_material_to_folder,
    move_video_to_folder,
    remove_generated_from_folder,
    remove_material_from_folder,
    remove_video_from_folder,
    update_folder,
)

router = APIRouter(prefix="/folders", tags=["文件夹管理"])


@router.get("")
def _list_folders(folder_type: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    return list_folders(db, folder_type, q)


@router.post("", status_code=201)
def _create_folder(name: str, folder_type: str = "video", db: Session = Depends(get_db)):
    return create_folder(db, name, folder_type)


@router.put("/{folder_id}")
def _update_folder(folder_id: int, name: str, db: Session = Depends(get_db)):
    return update_folder(db, folder_id, name)


@router.delete("/{folder_id}")
def _delete_folder(folder_id: int, db: Session = Depends(get_db)):
    return delete_folder(db, folder_id)


@router.put("/{folder_id}/videos/{video_id}")
def _move_video(folder_id: int, video_id: int, db: Session = Depends(get_db)):
    return move_video_to_folder(db, folder_id, video_id)


@router.put("/{folder_id}/materials/{material_id}")
def _move_material(folder_id: int, material_id: int, db: Session = Depends(get_db)):
    return move_material_to_folder(db, folder_id, material_id)


@router.put("/{folder_id}/generated/{gen_id}")
def _move_generated(folder_id: int, gen_id: int, db: Session = Depends(get_db)):
    return move_generated_to_folder(db, folder_id, gen_id)


@router.delete("/{folder_id}/videos/{video_id}")
def _remove_video_from_folder(folder_id: int, video_id: int, db: Session = Depends(get_db)):
    return remove_video_from_folder(db, video_id)


@router.delete("/{folder_id}/materials/{material_id}")
def _remove_material_from_folder(folder_id: int, material_id: int, db: Session = Depends(get_db)):
    return remove_material_from_folder(db, material_id)


@router.delete("/{folder_id}/generated/{gen_id}")
def _remove_generated_from_folder(folder_id: int, gen_id: int, db: Session = Depends(get_db)):
    return remove_generated_from_folder(db, gen_id)
