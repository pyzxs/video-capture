from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.services.export_service import export_files


class ExportRequest(BaseModel):
    video_ids: list[int] = []
    material_ids: list[int] = []
    generated_ids: list[int] = []
    dest_dir: str


router = APIRouter(prefix="/export", tags=["export"])


@router.post("")
def _export_files(req: ExportRequest, db: Session = Depends(get_db)):
    return export_files(db, req.video_ids, req.material_ids, req.generated_ids, req.dest_dir)
