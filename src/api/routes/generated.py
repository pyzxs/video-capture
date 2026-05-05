from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import (
    AutoBatchGenerateRequest,
    AutoGenerateRequest,
    GeneratedVideoCreate,
    GeneratedVideoUpdate,
    GenDubRequest,
)
from src.api.services.generated_service import (
    auto_batch_generate,
    auto_generate,
    auto_search,
    batch_generate_groups,
    create_generated,
    delete_generated,
    dub_generated_video,
    generate_video,
    get_generated,
    get_generated_file_path,
    list_generated,
    update_generated,
)

router = APIRouter(prefix="/generated", tags=["混剪视频管理"])


@router.get("")
def _list_generated(
    q: str | None = None,
    folder_id: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return list_generated(db, q, folder_id, status, skip, limit)


@router.post("/auto-search")
def _auto_search(data: AutoGenerateRequest):
    return auto_search(data)


@router.post("/auto-generate", status_code=201)
def _auto_generate(data: AutoGenerateRequest, db: Session = Depends(get_db)):
    return auto_generate(data, db)


@router.post("/auto-batch-generate", status_code=201)
def _auto_batch_generate(data: AutoBatchGenerateRequest, db: Session = Depends(get_db)):
    return auto_batch_generate(data, db)


@router.get("/{gen_id}")
def _get_generated(gen_id: int, db: Session = Depends(get_db)):
    return get_generated(db, gen_id)


@router.post("", status_code=201)
def _create_generated(data: GeneratedVideoCreate, db: Session = Depends(get_db)):
    return create_generated(db, data)


@router.put("/{gen_id}")
def _update_generated(gen_id: int, data: GeneratedVideoUpdate, db: Session = Depends(get_db)):
    return update_generated(db, gen_id, data)


@router.delete("/{gen_id}")
def _delete_generated(gen_id: int, db: Session = Depends(get_db)):
    return delete_generated(db, gen_id)


@router.post("/{gen_id}/generate")
def _generate_video(gen_id: int, voice: str | None = None, db: Session = Depends(get_db)):
    return generate_video(db, gen_id, voice)


@router.post("/{gen_id}/batch-generate-groups")
def _batch_generate_groups(gen_id: int, db: Session = Depends(get_db)):
    return batch_generate_groups(db, gen_id)


@router.post("/{gen_id}/dub")
def _dub_video(gen_id: int, data: GenDubRequest, db: Session = Depends(get_db)):
    return dub_generated_video(db, gen_id, data)


@router.get("/{gen_id}/download")
def _download_generated(gen_id: int, db: Session = Depends(get_db)):
    path = get_generated_file_path(db, gen_id)
    from pathlib import Path
    return FileResponse(path, media_type="video/mp4", filename=Path(path).name)
