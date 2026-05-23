import time

from fastapi import APIRouter, BackgroundTasks, Depends, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.response import response_success
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
    swap_material_filepath,
    update_material,
)
from src.api.services.subtitle_erase_service import submit_erase, query_erase, apply_erase
from src.db.engine import SessionLocal
from src.db.models import Material
from src.logger import get_logger

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


_active_erase_tasks: set[int] = set()


@router.post("/{material_id}/subtitle-erase", description="上传素材到 CMS 并提交字幕擦除任务，后台轮询完成自动替换")
def _submit_material_subtitle_erase(
    material_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if _active_erase_tasks:
        return response_success(status_code=400, message="有擦除任务正在执行中，请等待完成后再提交")

    filepath = get_material_file_path(db, material_id)
    result = submit_erase(filepath)
    task_id = result.get("task_id")
    cms_filepath = result.get("cms_filepath", "")
    if task_id:
        _active_erase_tasks.add(material_id)
        background_tasks.add_task(_background_poll_and_apply, task_id, material_id, filepath, cms_filepath)
    return response_success(data=result, message="字幕擦除任务已提交，后台处理中")


@router.put("/{material_id}/swap-filepath", description="切换 filepath 和 cms_filepath（原始文件 ↔ 擦除后文件）")
def _swap_material_filepath(material_id: int, db: Session = Depends(get_db)):
    return swap_material_filepath(db, material_id)


@router.get("/subtitle-erase/{task_id}", description="查询字幕擦除任务状态")
def _query_subtitle_erase(task_id: str):
    result = query_erase(task_id)
    return response_success(data=result, message="查询成功")


def _background_poll_and_apply(task_id: str, material_id: int, filepath: str, cms_filepath: str = ""):
    """后台轮询 CMS 擦除任务，完成后自动下载替换素材文件。"""
    logger = get_logger("subtitle_erase.bg")

    try:
        for i in range(120):
            time.sleep(10)
            try:
                result = query_erase(task_id, filepath=cms_filepath)
            except Exception as e:
                logger.warning("查询擦除任务失败 (attempt %d/120): %s", i + 1, e)
                continue

            status = result.get("status", "")
            if status == "completed":
                video_url = result.get("result", {}).get("video_url", "")
                if video_url:
                    db = SessionLocal()
                    try:
                        m = db.query(Material).get(material_id)
                        if m:
                            apply_erase(filepath, task_id, db, m, video_url=video_url)
                            logger.info("后台擦除完成: material_id=%d task_id=%s", material_id, task_id)
                    except Exception as e:
                        logger.error("后台擦除应用失败: %s", e)
                    finally:
                        db.close()
                return

            if status == "failed":
                logger.error("擦除任务失败: task_id=%s error=%s", task_id, result.get("error"))
                return

        logger.error("擦除任务超时: task_id=%s material_id=%d", task_id, material_id)
    except Exception as e:
        logger.error("后台擦除任务异常: %s", e)
    finally:
        _active_erase_tasks.discard(material_id)
