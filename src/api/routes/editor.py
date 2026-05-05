from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.services.editor_service import extract_subtitles, list_dir as list_directory


class ExtractSubtitlesRequest(BaseModel):
    clips: list[dict]
    language: str = "zh"


router = APIRouter(prefix="/editor", tags=["editor"])


@router.post("/extract-subtitles")
def _extract_subtitles(req: ExtractSubtitlesRequest, db: Session = Depends(get_db)):
    return extract_subtitles(req, db)


@router.get("/list-dir")
def _list_dir(dir: str):
    return list_directory(dir)
