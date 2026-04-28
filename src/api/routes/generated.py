import hashlib
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
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
from src.config import get_config
from src.logger import default_logger as logger
from src.utils import ensure_date_dir, generate_thumbnail, thumb_url
from src.db.models import GeneratedVideo

router = APIRouter(prefix="/generated", tags=["混剪视频管理"])


def _gen_to_dict(gen: GeneratedVideo) -> dict:
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
        "thumbnail": thumb_url(gen.thumbnail),
        "data": gen.data or "{}",
        "created_at": gen.created_at.isoformat() if gen.created_at else None,
        "completed_at": gen.completed_at.isoformat() if gen.completed_at else None,
    }
    return d


@router.get("")
def list_generated(
    q: str | None = None,
    folder_id: int | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(GeneratedVideo).order_by(GeneratedVideo.id.desc())
    if q:
        query = query.filter(GeneratedVideo.title.contains(q))
    if folder_id is not None:
        if folder_id == 0:
            query = query.filter(GeneratedVideo.folder_id.is_(None))
        else:
            query = query.filter(GeneratedVideo.folder_id == folder_id)
    total = query.count()
    gens = query.offset(skip).limit(limit).all()
    return {"items": [_gen_to_dict(g) for g in gens], "total": total}


@router.post("/auto-search")
def auto_search(data: AutoGenerateRequest, db: Session = Depends(get_db)):
    """自动检索素材：扩写(可选) → 分段 → 检索素材。返回脚本和素材列表，不生成视频。"""
    if not data.description:
        raise HTTPException(400, "请提供描述信息")

    from src.pipelines.generate import expand_and_search

    try:
        result = expand_and_search(
            query=data.description,
            skip_expand=data.skip_expand,
            script=data.script or None,
            frame_width=data.frame_width,
            frame_height=data.frame_height,
            frame_rate=data.frame_rate,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"自动检索失败: {e}")


def _execute_auto_generate(data: AutoGenerateRequest, db: Session) -> dict:
    """执行单次自动混剪，返回生成记录的字典。"""
    if not data.description:
        raise HTTPException(400, "请提供描述信息")

    import json, uuid

    # ── 1. 获取匹配素材（预选 or 自动检索） ──
    if data.material_ids:
        from src.db.models import Material
        mats = db.query(Material).filter(Material.id.in_(data.material_ids)).all()
        mat_map = {m.id: m for m in mats}
        matched_materials = []
        for mid in data.material_ids:
            m = mat_map.get(mid)
            if m and Path(m.filepath).exists():
                matched_materials.append({
                    "material_id": m.id,
                    "type": m.type,
                    "content": m.content,
                    "start_time": m.start_time,
                    "end_time": m.end_time,
                    "frame_width": m.frame_width or 0,
                    "frame_height": m.frame_height or 0,
                    "frame_rate": m.frame_rate or 0,
                    "filename": m.filename or "",
                    "filepath": m.filepath or "",
                })

        from src.services.llm import expand_text
        script = expand_text(data.description) if not data.skip_expand else (data.script or data.description)
    else:
        from src.pipelines.generate import expand_and_search
        search_result = expand_and_search(
            query=data.description,
            skip_expand=data.skip_expand,
            script=data.script or None,
            frame_width=data.frame_width,
            frame_height=data.frame_height,
            frame_rate=data.frame_rate,
        )
        matched_materials = search_result["materials"]
        script = search_result["script"]

    if not matched_materials:
        raise HTTPException(400, "未找到匹配素材")

    # ── 2. 收集源文件路径（去重，按素材顺序） ──
    from src.processing.ffmpeg import concat_videos, get_video_duration
    from src.services.tts import synthesize, dub_video

    clip_paths = []
    seen_paths = set()
    frame_rate_val = data.frame_rate or 30
    for r in matched_materials:
        fp = r.get("filepath", "")
        if fp and Path(fp).exists() and fp not in seen_paths:
            seen_paths.add(fp)
            clip_paths.append(fp)

    if not clip_paths:
        raise HTTPException(400, "素材文件不存在")

    # ── 3. 拼接视频 ──
    prefix_file = hashlib.md5((script + str(uuid.uuid4())).encode()).hexdigest()
    concat_output = str(ensure_date_dir(get_config("mixed_dir"), f"{prefix_file}_concat.mp4"))
    concat_videos(clip_paths, concat_output, data.frame_width, data.frame_height)

    # 计算视频总时长，限制脚本长度
    total_dur = get_video_duration(concat_output) or 30.0
    max_chars = int(total_dur * 4)
    if len(script) > max_chars:
        logger.info("  脚本 %d 字超过 %d 字限制（%.1fs × 4），截取前 %d 字", len(script), max_chars, total_dur, max_chars)
        script = script[:max_chars]

    # ── 4. 配音 ──
    audio_filepath = None
    tts_material_id = None
    if data.tts_voice:
        try:
            audio_filepath = synthesize(script, voice=data.tts_voice)
            try:
                from src.db.models import Material
                audio_dur = get_video_duration(audio_filepath)
                tts_material = Material(
                    type="audio",
                    content=script[:200],
                    start_time=0.0,
                    end_time=audio_dur,
                    filename=Path(audio_filepath).name,
                    filepath=audio_filepath,
                    status=0,
                )
                db.add(tts_material)
                db.flush()
                tts_material_id = tts_material.id
                logger.info("  → TTS 音频已存入素材库 #%d（status=0）", tts_material_id)
            except Exception as e:
                logger.warning("  → TTS 素材入库失败（不影响配音）: %s", e)
            final_output = str(ensure_date_dir(get_config("mixed_dir"), f"{prefix_file}_dubbed.mp4"))
            dub_video(concat_output, audio_filepath, output_path=final_output)
        except RuntimeError as e:
            logger.warning("  → 配音跳过: %s", e)
            final_output = concat_output
    else:
        final_output = concat_output

    # ── 5. 构建轨道数据（与视频编辑器格式一致） ──
    material_list = []
    current_frame = 0
    for r in matched_materials:
        dur = round(((r.get("end_time", 10) - r.get("start_time", 0)) or 10.0) * frame_rate_val)
        dur = max(dur, 30)
        material_list.append({
            "id": f"c-{uuid.uuid4().hex[:7]}",
            "type": r.get("type", "video"),
            "material_id": r["material_id"],
            "content": r.get("content", ""),
            "filepath": r.get("filepath", ""),
            "start": current_frame,
            "end": current_frame + dur,
            "frameCount": dur,
            "offsetL": 0, "offsetR": 0,
            "centerX": 50, "centerY": 50, "scale": 100,
            "width": r.get("frame_width", 1920) or 1920,
            "height": r.get("frame_height", 1080) or 1080,
            "fontSize": 48, "fontFamily": "sans-serif", "fontColor": "#ffffff",
            "bold": False, "italic": False,
            "shadow": False, "outline": False,
            "outlineColor": "#000000", "bgColor": "#000000",
            "bgEnabled": False, "textAlign": "center",
            "effect": "", "transitionIn": None,
        })
        current_frame += dur + 1

    tracks = [{"type": "video", "name": "主轨道", "list": material_list, "visible": True, "locked": False, "muted": True}]
    if audio_filepath and Path(audio_filepath).exists():
        audio_dur_frames = round(get_video_duration(audio_filepath) * frame_rate_val)
        tracks.append({
            "type": "audio", "name": "配音", "list": [{
                "id": f"c-{uuid.uuid4().hex[:7]}",
                "type": "audio",
                "material_id": tts_material_id,
                "content": "配音",
                "filepath": audio_filepath,
                "start": 0, "end": audio_dur_frames,
                "frameCount": audio_dur_frames,
                "offsetL": 0, "offsetR": 0,
                "centerX": 50, "centerY": 50, "scale": 100,
            }], "visible": False, "locked": False, "muted": False,
        })

    # ── 6. 创建混剪记录 ──
    gen = GeneratedVideo(
        title=data.title or data.description,
        script=script,
        tts_voice=data.tts_voice or "",
        output_filepath=final_output,
        status="completed",
        frame_width=data.frame_width or 0,
        frame_height=data.frame_height or 0,
        frame_rate=frame_rate_val,
        material_count=len(matched_materials),
        thumbnail=generate_thumbnail(final_output),
        data=json.dumps({"tracks": tracks}, ensure_ascii=False),
        folder_id=data.folder_id,
        completed_at=datetime.utcnow(),
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)

    return _gen_to_dict(gen)


@router.post("/auto-generate", status_code=201)
def auto_generate(data: AutoGenerateRequest, db: Session = Depends(get_db)):
    """自动混剪：扩写(可选) → 分段 → 检索素材 → 构建轨道数据 → 合成。"""
    try:
        return _execute_auto_generate(data, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"自动混剪失败: {e}")


@router.post("/auto-batch-generate", status_code=201)
def auto_batch_generate(data: AutoBatchGenerateRequest, db: Session = Depends(get_db)):
    """批次自动混剪：使用多线程并行生成多个混剪视频。

    count=1 时与 auto-generate 行为一致（单次生成）。
    count>1 时启动 count 个线程并行执行，每个线程使用独立的数据库会话。
    """
    count = max(1, min(data.count, 50))

    if count == 1:
        try:
            result = _execute_auto_generate(data, db)
            return {"count": 1, "results": [result]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"自动混剪失败: {e}")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.db.engine import SessionLocal

    results = []
    errors = []

    def _worker():
        thread_db = SessionLocal()
        try:
            return _execute_auto_generate(data, thread_db)
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=min(count, 10)) as executor:
        futures = [executor.submit(_worker) for _ in range(count)]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except HTTPException as e:
                errors.append(str(e.detail))
            except Exception as e:
                errors.append(str(e))

    return {
        "count": len(results),
        "total": count,
        "results": results,
        "errors": errors if errors else None,
    }


@router.get("/{gen_id}")
def get_generated(gen_id: int, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    return _gen_to_dict(gen)


@router.post("", status_code=201)
def create_generated(data: GeneratedVideoCreate, db: Session = Depends(get_db)):
    gen = GeneratedVideo(
        title=data.title,
        script=data.script,
        tts_voice=data.tts_voice,
        output_filepath=data.output_filepath,
        data=data.data or "{}",
        frame_width=data.frame_width,
        frame_height=data.frame_height,
        status="created",
        folder_id=data.folder_id,
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)
    return _gen_to_dict(gen)


@router.put("/{gen_id}")
def update_generated(gen_id: int, data: GeneratedVideoUpdate, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)

    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(gen, field, value)

    db.commit()
    db.refresh(gen)
    return _gen_to_dict(gen)


@router.delete("/{gen_id}")
def delete_generated(gen_id: int, db: Session = Depends(get_db)):
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    db.delete(gen)
    db.commit()
    return {"ok": True}


def _execute_generate(gen: GeneratedVideo, db: Session, voice: str | None = None) -> GeneratedVideo:
    """从 data JSON 读取剪辑信息 → 拼接素材 → 可选配音（共用核心逻辑）。"""
    import json
    try:
        clip_data = json.loads(gen.data) if gen.data else {}
    except Exception:
        clip_data = {}
    tracks = clip_data.get("tracks", [])

    from src.db.models import Material
    from src.processing.ffmpeg import mix_audio_tracks, concat_videos
    from src.processing.ffmpeg import ffmpeg_prefix as ff

    fps = gen.frame_rate or 30
    target_w = gen.frame_width or None
    target_h = gen.frame_height or None

    import subprocess, uuid
    temp_dir = ensure_date_dir(get_config("mixed_dir"), "segments")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    segment_paths = []
    audio_paths = []

    for track in tracks:
        for clip in track.get("list", []):
            ctype = clip.get("type", "")
            if ctype == "text":
                continue

            fp = clip.get("filepath", "")
            if not fp or not Path(fp).exists():
                mid = clip.get("material_id")
                if mid is not None:
                    m = db.query(Material).get(mid)
                    if m and Path(m.filepath).exists():
                        fp = m.filepath
            if not fp or not Path(fp).exists():
                continue

            if ctype == "audio":
                audio_paths.append(fp)
                continue

            # --- 计算时间裁剪 ---
            start_frame = clip.get("start", 0) or 0
            end_frame = clip.get("end", 0) or 0
            offset_l = clip.get("offsetL", 0) or 0
            offset_r = clip.get("offsetR", 0) or 0
            adj_start = max(start_frame + offset_l, 0)
            adj_end = max(end_frame - offset_r, adj_start + 1)
            start_sec = adj_start / fps
            dur_sec = (adj_end - adj_start) / fps

            is_image = fp.lower().endswith(('.jpg', '.png', '.jpeg'))

            if is_image:
                segment_paths.append(fp)
                continue

            seg_path = str(Path(temp_dir) / f"seg_{gen.id}_{uuid.uuid4().hex[:8]}.mp4")
            cmd = [
                f"{ff}ffmpeg", "-y",
                "-ss", f"{start_sec:.3f}",
                "-i", str(fp),
                "-t", f"{dur_sec:.3f}",
                "-c:v", "libx264", "-crf", "18",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                "-avoid_negative_ts", "make_zero",
                str(seg_path),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                # 验证裁剪出的片段包含有效的媒体流（避免 header-only 文件导致 concat 失败）
                valid = False
                try:
                    probe = subprocess.run(
                        [f"{ff}ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                         "-of", "csv=p=0", str(seg_path)],
                        capture_output=True, text=True, timeout=10,
                    )
                    valid = bool(probe.stdout.strip())
                except Exception:
                    pass
                if valid:
                    segment_paths.append(seg_path)
                else:
                    logger.warning("裁剪素材无有效媒体流 %s", fp)
                    Path(seg_path).unlink(missing_ok=True)
            except subprocess.CalledProcessError as e:
                logger.warning("裁剪素材失败 %s: %s", fp, e.stderr[-200:] if e.stderr else "")
                Path(seg_path).unlink(missing_ok=True)

    if not segment_paths:
        raise HTTPException(400, "没有素材可供拼接")

    output = str(ensure_date_dir(get_config("mixed_dir"), f"remix_{gen.id}.mp4"))
    concat_videos(segment_paths, output, target_width=target_w, target_height=target_h)

    for sp in segment_paths:
        try:
            if sp.startswith(str(temp_dir)):
                Path(sp).unlink(missing_ok=True)
        except Exception:
            pass

    if audio_paths:
        try:
            output = mix_audio_tracks(output, audio_paths)
        except Exception as e:
            logger.warning("音频混入失败（不影响生成）: %s", e)

    if voice:
        from src.services.tts import dub_from_text
        if gen.script:
            try:
                dubbed = str(ensure_date_dir(get_config("mixed_dir"), f"remix_{gen.id}_dubbed.mp4"))
                dub_from_text(output, gen.script, voice=voice, output_path=dubbed)
                output = dubbed
                gen.tts_voice = voice
            except Exception as e:
                logger.warning("配音失败（不影响生成）: %s", e)
        else:
            logger.warning("没有配音脚本，跳过配音")

    gen.status = "completed"
    gen.output_filepath = output
    gen.thumbnail = generate_thumbnail(output)
    db.commit()
    return gen


@router.post("/{gen_id}/generate")
def generate_video(
    gen_id: int,
    voice: str | None = None,
    db: Session = Depends(get_db),
):
    """执行混剪：从 data JSON 读取剪辑信息 → 拼接素材 → 可选配音。"""
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    return _gen_to_dict(_execute_generate(gen, db, voice))


@router.post("/{gen_id}/dub")
def dub_video(gen_id: int, data: GenDubRequest, db: Session = Depends(get_db)):
    """为混剪视频配音。"""
    from src.services.tts import dub_from_text

    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise HTTPException(404, "混剪视频不存在")
    if not gen.output_filepath or not Path(gen.output_filepath).exists():
        raise HTTPException(400, "请先生成视频")
    if not gen.script:
        raise HTTPException(400, "没有配音文本")

    try:
        final = str(ensure_date_dir(get_config("mixed_dir"), f"remix_{gen_id}_dubbed.mp4"))
        dub_from_text(
            gen.output_filepath,
            gen.script,
            voice=data.voice,
            output_path=final,
        )
        gen.output_filepath = final
        gen.tts_voice = data.voice or ""
        db.commit()
        return _gen_to_dict(gen)
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
