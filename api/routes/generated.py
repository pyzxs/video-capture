from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import (
    AutoGenerateRequest,
    GeneratedVideoCreate,
    GeneratedVideoOut,
    GeneratedVideoUpdate,
    GenDubRequest,
    GenMaterialAdd,
    GenMaterialRemove,
    GenMaterialReorder,
)
from src.config import OUTPUT_DIR
from src.models.models import GeneratedVideo, GeneratedVideoMaterial, Material

router = APIRouter(prefix="/generated", tags=["混剪视频管理"])


def _load_materials(gen: GeneratedVideo, db: Session) -> list[dict]:
    """加载混剪视频的关联素材列表（按顺序）。"""
    assocs = (
        db.query(GeneratedVideoMaterial)
        .filter(GeneratedVideoMaterial.generated_video_id == gen.id)
        .order_by(GeneratedVideoMaterial.sequence_order)
        .all()
    )
    materials = []
    for a in assocs:
        m = db.query(Material).get(a.material_id)
        materials.append({
            "material_id": a.material_id,
            "sequence_order": a.sequence_order,
            "segment_start_time": a.segment_start_time,
            "segment_end_time": a.segment_end_time,
            "content": m.content if m else "",
            "filepath": m.filepath if m else "",
        })
    return materials


def _gen_to_dict(gen: GeneratedVideo, db: Session) -> dict:
    d = {
        "id": gen.id,
        "title": gen.title,
        "script": gen.script,
        "tts_voice": gen.tts_voice,
        "output_filepath": gen.output_filepath,
        "duration": gen.duration,
        "frame_width": gen.frame_width,
        "frame_height": gen.frame_height,
        "frame_rate": gen.frame_rate,
        "status": gen.status,
        "error_message": gen.error_message,
        "material_count": gen.material_count,
        "created_at": gen.created_at.isoformat() if gen.created_at else None,
        "completed_at": gen.completed_at.isoformat() if gen.completed_at else None,
        "materials": _load_materials(gen, db),
    }
    return d


@router.get("")
def list_generated(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(GeneratedVideo).order_by(GeneratedVideo.id.desc())
    total = query.count()
    gens = query.offset(skip).limit(limit).all()
    return {"items": [_gen_to_dict(g, db) for g in gens], "total": total}


@router.post("/auto-generate", status_code=201)
def auto_generate(data: AutoGenerateRequest, db: Session = Depends(get_db)):
    """自动混剪：LLM 扩写 → 分段 → 检索素材 → 拼接 → 配音。"""
    if not data.description:
        raise HTTPException(400, "请提供描述信息")

    from src.pipeline import search_and_generate

    try:
        result = search_and_generate(
            query=data.description,
            frame_width=data.frame_width,
            frame_height=data.frame_height,
            frame_rate=data.frame_rate,
        )
        if "error" in result:
            raise HTTPException(400, result["error"])

        # search_and_generate 已在内部创建记录，找到最新那条更新标题
        gen = db.query(GeneratedVideo).order_by(GeneratedVideo.id.desc()).first()
        if gen and data.title and gen.title != data.title:
            gen.title = data.title
            gen.tts_voice = data.tts_voice or gen.tts_voice
            db.commit()

        if gen:
            return _gen_to_dict(gen, db)

        return {
            "script": result.get("script", ""),
            "material_count": result.get("material_count", 0),
            "output_video": result.get("output_video", ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"自动混剪失败: {e}")


@router.get("/{gen_id}")
def get_generated(gen_id: int, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    return _gen_to_dict(gen, db)


@router.post("", status_code=201)
def create_generated(data: GeneratedVideoCreate, db: Session = Depends(get_db)):
    gen = GeneratedVideo(
        title=data.title,
        script=data.script,
        tts_voice=data.tts_voice,
        output_filepath=data.output_filepath,
        status="created",
        material_count=len(data.material_ids),
    )
    db.add(gen)
    db.flush()

    for i, mid in enumerate(data.material_ids):
        m = db.query(Material).get(mid)
        assoc = GeneratedVideoMaterial(
            generated_video_id=gen.id,
            material_id=mid,
            sequence_order=i,
            segment_start_time=m.start_time if m else 0,
            segment_end_time=m.end_time if m else 0,
        )
        db.add(assoc)

    db.commit()
    db.refresh(gen)
    return _gen_to_dict(gen, db)


@router.put("/{gen_id}")
def update_generated(gen_id: int, data: GeneratedVideoUpdate, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(gen, field, value)
    db.commit()
    db.refresh(gen)
    return _gen_to_dict(gen, db)


@router.delete("/{gen_id}")
def delete_generated(gen_id: int, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    db.query(GeneratedVideoMaterial).filter(
        GeneratedVideoMaterial.generated_video_id == gen_id
    ).delete()
    db.delete(gen)
    db.commit()
    return {"ok": True}


# ── 素材编排 ──

@router.post("/{gen_id}/materials")
def add_material(gen_id: int, data: GenMaterialAdd, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    m = db.query(Material).get(data.material_id)
    if not m:
        raise HTTPException(404, "素材不存在")

    max_order = (
        db.query(GeneratedVideoMaterial.sequence_order)
        .filter(GeneratedVideoMaterial.generated_video_id == gen_id)
        .order_by(GeneratedVideoMaterial.sequence_order.desc())
        .first()
    )
    next_order = (max_order[0] + 1) if max_order else 0

    assoc = GeneratedVideoMaterial(
        generated_video_id=gen_id,
        material_id=data.material_id,
        sequence_order=next_order,
        segment_start_time=m.start_time,
        segment_end_time=m.end_time,
    )
    db.add(assoc)
    gen.material_count = gen.material_count + 1
    db.commit()
    return _gen_to_dict(gen, db)


@router.delete("/{gen_id}/materials/{material_id}")
def remove_material(gen_id: int, material_id: int, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    assoc = (
        db.query(GeneratedVideoMaterial)
        .filter(
            GeneratedVideoMaterial.generated_video_id == gen_id,
            GeneratedVideoMaterial.material_id == material_id,
        )
        .first()
    )
    if not assoc:
        raise HTTPException(404, "关联不存在")
    db.delete(assoc)
    gen.material_count = max(0, gen.material_count - 1)
    db.commit()
    return _gen_to_dict(gen, db)


@router.put("/{gen_id}/reorder")
def reorder_materials(gen_id: int, data: GenMaterialReorder, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    for i, mid in enumerate(data.material_ids):
        assoc = (
            db.query(GeneratedVideoMaterial)
            .filter(
                GeneratedVideoMaterial.generated_video_id == gen_id,
                GeneratedVideoMaterial.material_id == mid,
            )
            .first()
        )
        if assoc:
            assoc.sequence_order = i
    db.commit()
    return _gen_to_dict(gen, db)


@router.post("/{gen_id}/generate")
def generate_video(gen_id: int, db: Session = Depends(get_db)):
    """执行混剪：拼接素材 + 配音。"""
    from src.pipeline import search_and_generate

    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")

    assocs = (
        db.query(GeneratedVideoMaterial)
        .filter(GeneratedVideoMaterial.generated_video_id == gen_id)
        .order_by(GeneratedVideoMaterial.sequence_order)
        .all()
    )
    if not assocs:
        raise HTTPException(400, "没有素材可供拼接")

    # 收集素材路径
    clip_paths = []
    for a in assocs:
        m = db.query(Material).get(a.material_id)
        if m and Path(m.filepath).exists():
            clip_paths.append(m.filepath)

    if not clip_paths:
        raise HTTPException(400, "素材文件不存在")

    from src.query.video_synth import concat_videos

    output = str(OUTPUT_DIR / f"remix_{gen_id}.mp4")
    concat_videos(clip_paths, output)

    gen.status = "completed"
    gen.output_filepath = output
    db.commit()

    return _gen_to_dict(gen, db)


@router.post("/{gen_id}/dub")
def dub_video(gen_id: int, data: GenDubRequest, db: Session = Depends(get_db)):
    """为混剪视频配音。"""
    from src.tts.cosyvoice import dub_from_text

    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    if not gen.output_filepath or not Path(gen.output_filepath).exists():
        raise HTTPException(400, "请先生成视频")
    if not gen.script:
        raise HTTPException(400, "没有配音文本")

    try:
        final = str(OUTPUT_DIR / f"remix_{gen_id}_dubbed.mp4")
        dub_from_text(
            gen.output_filepath,
            gen.script,
            voice=data.voice,
            output_path=final,
        )
        gen.output_filepath = final
        gen.tts_voice = data.voice or ""
        db.commit()
        return _gen_to_dict(gen, db)
    except Exception as e:
        raise HTTPException(500, f"配音失败: {e}")


@router.get("/{gen_id}/download")
def download_generated(gen_id: int, db: Session = Depends(get_db)):
    """下载生成的混剪视频文件。"""
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    if not gen.output_filepath or not Path(gen.output_filepath).exists():
        raise HTTPException(404, "视频文件不存在")
    return FileResponse(
        gen.output_filepath,
        media_type="video/mp4",
        filename=Path(gen.output_filepath).name,
    )
