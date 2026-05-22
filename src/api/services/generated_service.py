"""Generated video business logic: CRUD, auto-generate, batch, groups, ASS helpers."""
import hashlib
import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.api.schemas import (
    AutoBatchGenerateRequest,
    AutoGenerateRequest,
    GeneratedVideoCreate,
    GeneratedVideoUpdate,
    GenDubRequest,
)
from src.config import get_config
from src.db.models import GeneratedVideo, Material
from src.logger import default_logger as logger

from src.utils import ensure_date_dir, generate_thumbnail, thumb_url, _CREATIONFLAGS


# ── helpers ──

def _gen_to_dict(gen: GeneratedVideo) -> dict:
    return {
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


def _format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _hex_to_ass_bgr(hex_color: str) -> str:
    if hex_color.startswith("#") and len(hex_color) >= 7:
        r, g, b = hex_color[1:3], hex_color[3:5], hex_color[5:7]
        return f"&H{b}{g}{r}&"
    return "&HFFFFFF&"


def _parse_rgba(rgba_str: str):
    if not rgba_str:
        return 0, 0, 0, 0
    s = rgba_str.strip()
    if s.startswith("rgba"):
        parts = s[5:-1].split(",")
        if len(parts) >= 4:
            return int(parts[0]), int(parts[1]), int(parts[2]), int(float(parts[3]) * 255)
    if s.startswith("#"):
        if len(s) >= 7:
            return int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16), 255
    return 0, 0, 0, 0


def _clip_ass_style(clip: dict, canvas_w: int, canvas_h: int) -> str:
    codes = []

    ff = clip.get("fontFamily") or "sans-serif"
    fs = clip.get("fontSize") or 48
    codes.append(f"\\fn{ff}")
    codes.append(f"\\fs{fs}")

    fc = clip.get("fontColor") or "#ffffff"
    codes.append(f"\\c{_hex_to_ass_bgr(fc)}")

    codes.append("\\b1" if clip.get("bold") else "\\b0")
    codes.append("\\i1" if clip.get("italic") else "\\i0")

    if clip.get("outline"):
        oc = clip.get("outlineColor") or "#000000"
        codes.append("\\bord2")
        codes.append(f"\\3c{_hex_to_ass_bgr(oc)}")
    else:
        codes.append("\\bord0")

    codes.append("\\shad2" if clip.get("shadow") else "\\shad0")

    if clip.get("bgEnabled"):
        r, g, b, a = _parse_rgba(clip.get("bgColor"))
        if a > 0:
            codes.append("\\bord3")
            codes.append(f"\\3c&H{b:02X}{g:02X}{r:02X}&")
            codes.append(f"\\1a&H{255 - a:02X}&")

    ta = clip.get("textAlign") or "center"
    cx = (clip.get("centerX") or 50) / 100
    cy = (clip.get("centerY") or 50) / 100
    x = int(canvas_w * cx)
    y = int(canvas_h * cy)
    codes.append(f"\\pos({x},{y})")
    if ta == "left":
        codes.append("\\an1")
    elif ta == "right":
        codes.append("\\an3")
    else:
        codes.append("\\an5")

    return "{" + "".join(codes) + "}"


def _write_ass(text_clips: list[dict], fps: float, output_path: str, canvas_w: int = 1920, canvas_h: int = 1080):
    entries = []
    for clip in text_clips:
        content = clip.get("content", "").strip()
        if not content:
            continue
        start_frame = clip.get("start", 0) or 0
        end_frame = clip.get("end", 0) or 0
        if end_frame <= start_frame:
            continue
        start_sec = start_frame / fps
        end_sec = end_frame / fps
        style = _clip_ass_style(clip, canvas_w, canvas_h)
        entries.append((start_sec, end_sec, style, content))

    entries.sort(key=lambda e: e[0])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write(f"PlayResX: {canvas_w}\n")
        f.write(f"PlayResY: {canvas_h}\n")
        f.write("WrapStyle: 2\n\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                 "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                 "Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Noto Sans SC,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
                 "0,0,0,0,100,100,0,0,1,1,1,2,10,10,10,1\n\n")
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for start_sec, end_sec, style, content in entries:
            start_ts = _format_ass_time(start_sec)
            end_ts = _format_ass_time(end_sec)
            f.write(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{style}{content}\n")


def _write_asr_ass(segments: list[dict], output_path: str, canvas_w: int = 1920, canvas_h: int = 1080):
    """Write ASR subtitle segments as an ASS subtitle file with centered bottom text."""
    entries = []
    for seg in segments:
        start = seg.get("start", 0) or 0
        end = seg.get("end", 0) or 0
        text = seg.get("text", "").strip()
        if not text or end <= start:
            continue
        entries.append((start, end, text))

    entries.sort(key=lambda e: e[0])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write(f"PlayResX: {canvas_w}\n")
        f.write(f"PlayResY: {canvas_h}\n")
        f.write("WrapStyle: 2\n\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                 "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                 "Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Noto Sans SC,36,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
                 "0,0,0,0,100,100,0,0,1,0,0,2,10,10,10,1\n\n")
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for start_sec, end_sec, text in entries:
            start_ts = _format_ass_time(start_sec)
            end_ts = _format_ass_time(end_sec)
            f.write(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}\n")


def _sync_text_materials(data_json: str, frame_width: int, frame_height: int, db: Session) -> str:
    try:
        data = json.loads(data_json) if data_json else {}
    except Exception:
        return data_json

    tracks = data.get("tracks", [])
    modified = False
    for track in tracks:
        for clip in track.get("list", []):
            if clip.get("type") != "text":
                continue
            content = (clip.get("content") or "").strip()
            if not content:
                continue

            mid = clip.get("material_id")
            mat = None
            if mid:
                mat = db.query(Material).get(mid)
            if mat:
                mat.content = content
            else:
                mat = Material(
                    type="text",
                    content=content,
                    status=0,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )
                db.add(mat)
                db.flush()
                clip["material_id"] = mat.id
                modified = True

    if modified:
        return json.dumps(data, ensure_ascii=False)
    return data_json


def _make_segment(clip: dict, fp: str, fps: int, gen_id: int, temp_dir: str) -> str | None:
    import subprocess
    from src.processing.ffmpeg import FFMPEG, FFPROBE

    start_frame = clip.get("start", 0) or 0
    end_frame = clip.get("end", 0) or 0
    offset_l = clip.get("offsetL", 0) or 0
    offset_r = clip.get("offsetR", 0) or 0
    clip_dur = end_frame - start_frame
    adj_start = max(offset_l, 0)
    adj_end = max(offset_l + clip_dur - offset_r, adj_start + 1)
    start_sec = adj_start / fps
    dur_sec = (adj_end - adj_start) / fps

    is_image = fp.lower().endswith(('.jpg', '.png', '.jpeg'))
    if is_image:
        return fp

    seg_path = str(Path(temp_dir) / f"seg_{gen_id}_{uuid.uuid4().hex[:8]}.mp4")
    cmd = [
        FFMPEG, "-y",
        "-ss", f"{start_sec:.3f}",
        "-i", str(fp),
        "-t", f"{dur_sec:.3f}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-avoid_negative_ts", "make_zero",
        str(seg_path),
    ]
    try:
        subprocess.run(cmd, creationflags=_CREATIONFLAGS, check=True, capture_output=True)
        valid = False
        try:
            probe = subprocess.run(
                [FFPROBE, "-v", "error", "-show_entries", "stream=codec_type",
                 "-of", "csv=p=0", str(seg_path)],
                creationflags=_CREATIONFLAGS, capture_output=True, text=True, timeout=10,
            )
            valid = bool(probe.stdout.strip())
        except Exception:
            pass
        if valid:
            return seg_path
        else:
            logger.warning("裁剪素材无有效媒体流 %s", fp)
            Path(seg_path).unlink(missing_ok=True)
            return None
    except subprocess.CalledProcessError as e:
        logger.warning("裁剪素材失败 %s: %s", fp, e.stderr[-200:] if e.stderr else "")
        Path(seg_path).unlink(missing_ok=True)
        return None


def _extract_audio_segment(fp: str, duration_sec: float, gen_id: int, temp_dir: str) -> str | None:
    import subprocess
    from src.processing.ffmpeg import FFMPEG, FFPROBE

    seg_path = str(Path(temp_dir) / f"aud_{gen_id}_{uuid.uuid4().hex[:8]}.wav")
    cmd = [
        FFMPEG, "-y",
        "-ss", "0",
        "-i", str(fp),
        "-t", f"{duration_sec:.3f}",
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "44100", "-ac", "2",
        str(seg_path),
    ]
    try:
        subprocess.run(cmd, creationflags=_CREATIONFLAGS, check=True, capture_output=True)
        if Path(seg_path).exists() and Path(seg_path).stat().st_size > 0:
            return seg_path
        else:
            Path(seg_path).unlink(missing_ok=True)
            return None
    except subprocess.CalledProcessError as e:
        logger.warning("提取音频片段失败 %s: %s", fp, e.stderr[-200:] if e.stderr else "")
        Path(seg_path).unlink(missing_ok=True)
        return None


# ── CRUD ──

def list_generated(
    db: Session,
    q: str | None = None,
    folder_id: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    query = db.query(GeneratedVideo).order_by(GeneratedVideo.id.desc())
    if q:
        query = query.filter(GeneratedVideo.title.contains(q))
    if status:
        query = query.filter(GeneratedVideo.status == status)
    if folder_id is not None:
        if folder_id == 0:
            query = query.filter(GeneratedVideo.folder_id.is_(None))
        else:
            query = query.filter(GeneratedVideo.folder_id == folder_id)
    total = query.count()
    gens = query.offset(skip).limit(limit).all()
    return {"items": [_gen_to_dict(g) for g in gens], "total": total}


def get_generated(db: Session, gen_id: int) -> dict:
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise fail_response(status_code=404, message="混剪视频不存在")
    return _gen_to_dict(gen)


def create_generated(db: Session, data: GeneratedVideoCreate) -> dict:
    synced_data = _sync_text_materials(data.data or "{}", data.frame_width, data.frame_height, db)
    gen = GeneratedVideo(
        title=data.title,
        script=data.script,
        tts_voice=data.tts_voice,
        output_filepath=data.output_filepath,
        data=synced_data,
        frame_width=data.frame_width,
        frame_height=data.frame_height,
        status="created",
        folder_id=data.folder_id,
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)
    return _gen_to_dict(gen)


def update_generated(db: Session, gen_id: int, data: GeneratedVideoUpdate) -> dict:
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise fail_response(status_code=404, message="混剪视频不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "data":
            value = _sync_text_materials(value or "{}", data.frame_width or 0, data.frame_height or 0, db)
        setattr(gen, field, value)
    db.commit()
    db.refresh(gen)
    return _gen_to_dict(gen)


def delete_generated(db: Session, gen_id: int) -> dict:
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise fail_response(status_code=404, message="混剪视频不存在")
    if gen.output_filepath and Path(gen.output_filepath).exists():
        Path(gen.output_filepath).unlink(missing_ok=True)
    db.delete(gen)
    db.commit()
    return {"ok": True}


def get_generated_file_path(db: Session, gen_id: int) -> str:
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise fail_response(status_code=404, message="混剪视频不存在")
    if not gen.output_filepath or not Path(gen.output_filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")
    return gen.output_filepath


# ── Auto search / generate ──

def auto_search(data: AutoGenerateRequest) -> dict:
    if not data.description:
        raise fail_response(status_code=400, message="请提供描述信息")

    from src.pipelines.generate import expand_and_search

    try:
        return expand_and_search(
            query=data.description,
            skip_expand=data.skip_expand,
            script=data.script or None,
            frame_width=data.frame_width,
            frame_height=data.frame_height,
            frame_rate=data.frame_rate,
        )
    except Exception as e:
        raise fail_response(status_code=500, message=f"自动检索失败: {e}")


def _execute_auto_generate(data: AutoGenerateRequest, db: Session, batch_index: int = 0) -> dict:
    if not data.description:
        raise fail_response(status_code=400, message="请提供描述信息")

    from src.processing.ffmpeg import concat_videos, get_video_duration
    from src.services.tts import synthesize, dub_video

    # 1. 获取匹配素材（预选 or 自动检索）
    if data.material_ids:
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
        raise fail_response(status_code=400, message="未找到匹配素材")

    # 批量模式：打乱素材顺序以产生不同的视频和文案
    if batch_index > 0:
        import random
        matched_materials = list(matched_materials)
        random.shuffle(matched_materials)

    # 2. 收集源文件路径（去重，按素材顺序）
    clip_paths = []
    seen_paths = set()
    frame_rate_val = data.frame_rate or 30
    for r in matched_materials:
        fp = r.get("filepath", "")
        if fp and Path(fp).exists() and fp not in seen_paths:
            seen_paths.add(fp)
            clip_paths.append(fp)

    if not clip_paths:
        raise fail_response(status_code=400, message="素材文件不存在")

    # 3. 拼接视频
    prefix_file = hashlib.md5((script + str(uuid.uuid4())).encode()).hexdigest()
    concat_output = str(ensure_date_dir(get_config("mixed_dir"), f"{prefix_file}_concat.mp4"))
    concat_videos(clip_paths, concat_output, data.frame_width, data.frame_height)

    total_dur = get_video_duration(concat_output) or 30.0

    # 3.5 根据核心主题 + 素材文案 + 视频时长，生成配音脚本
    from src.services.llm import refine_dubbing_script
    material_texts = [r.get("content", "") for r in matched_materials]
    script = refine_dubbing_script(data.description, material_texts, total_dur, variation=batch_index)
    logger.info("  配音脚本 %d 字（视频 %.1fs, batch=%d）", len(script), total_dur, batch_index)

    # 4. 配音
    audio_filepath = None
    tts_material_id = None
    if data.tts_voice:
        try:
            audio_filepath = synthesize(script, voice=data.tts_voice)
            try:
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

    # 4.5 混入背景音频（在配音之后，确保不被 dub_video 覆盖）
    if data.audio_material_id:
        audio_mat = db.query(Material).get(data.audio_material_id)
        if audio_mat and Path(audio_mat.filepath).exists():
            try:
                from src.processing.ffmpeg import mix_audio_tracks
                has_dubbing = audio_filepath and Path(audio_filepath).exists()
                bg_vol = 0.2 if has_dubbing else 1.0
                final_output = mix_audio_tracks(final_output, [audio_mat.filepath], bg_volume=bg_vol)
                logger.info("  → 已混入背景音频 (vol=%.1f): %s", bg_vol, audio_mat.filename or audio_mat.filepath)
            except Exception as e:
                logger.warning("  → 背景音频混入失败: %s", e)

    # 5. 构建轨道数据
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

    # 6. 创建混剪记录
    final_duration = get_video_duration(final_output) or 0.0
    from src.services.llm import generate_title
    title = data.title or generate_title(script, matched_materials)
    gen = GeneratedVideo(
        title=title,
        script=script,
        tts_voice=data.tts_voice or "",
        output_filepath=final_output,
        duration=final_duration,
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


def auto_generate(data: AutoGenerateRequest, db: Session) -> dict:
    try:
        return _execute_auto_generate(data, db)
    except HTTPException:
        raise
    except Exception as e:
        raise fail_response(status_code=500, message=f"自动混剪失败: {e}")


def auto_batch_generate(data: AutoBatchGenerateRequest, db: Session) -> dict:
    count = max(1, min(data.count, 50))

    if count == 1:
        try:
            result = _execute_auto_generate(data, db)
            return {"count": 1, "results": [result]}
        except HTTPException:
            raise
        except Exception as e:
            raise fail_response(status_code=500, message=f"自动混剪失败: {e}")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.db.engine import SessionLocal

    results = []
    errors = []

    def _worker(idx):
        thread_db = SessionLocal()
        try:
            return _execute_auto_generate(data, thread_db, batch_index=idx)
        finally:
            thread_db.close()

    with ThreadPoolExecutor(max_workers=min(count, 10)) as executor:
        futures = [executor.submit(_worker, i) for i in range(count)]
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


# ── Generate from editor data ──

def _execute_generate(gen: GeneratedVideo, db: Session, voice: str | None = None) -> GeneratedVideo:
    import subprocess
    from src.processing.ffmpeg import mix_audio_tracks, concat_videos
    from src.processing.ffmpeg import FFMPEG, FFPROBE

    try:
        clip_data = json.loads(gen.data) if gen.data else {}
    except Exception:
        clip_data = {}
    tracks = clip_data.get("tracks", [])

    fps = gen.frame_rate or 30
    target_w = gen.frame_width or None
    target_h = gen.frame_height or None

    temp_dir = ensure_date_dir(get_config("mixed_dir"), "segments")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    segment_paths = []
    audio_paths = []
    text_clips = []

    for track in tracks:
        for clip in track.get("list", []):
            ctype = clip.get("type", "")
            if ctype == "text":
                text_clips.append(clip)
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

            start_frame = clip.get("start", 0) or 0
            end_frame = clip.get("end", 0) or 0
            offset_l = clip.get("offsetL", 0) or 0
            offset_r = clip.get("offsetR", 0) or 0
            clip_dur = end_frame - start_frame
            adj_start = max(offset_l, 0)
            adj_end = max(offset_l + clip_dur - offset_r, adj_start + 1)
            start_sec = adj_start / fps
            dur_sec = (adj_end - adj_start) / fps

            is_image = fp.lower().endswith(('.jpg', '.png', '.jpeg'))

            if is_image:
                segment_paths.append(fp)
                continue

            seg_path = str(Path(temp_dir) / f"seg_{gen.id}_{uuid.uuid4().hex[:8]}.mp4")
            cmd = [
                FFMPEG, "-y",
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
                subprocess.run(cmd, creationflags=_CREATIONFLAGS, check=True, capture_output=True)
                valid = False
                try:
                    probe = subprocess.run(
                        [FFPROBE, "-v", "error", "-show_entries", "stream=codec_type",
                         "-of", "csv=p=0", str(seg_path)],
                        creationflags=_CREATIONFLAGS, capture_output=True, text=True, timeout=10,
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
        raise fail_response(status_code=400, message="没有素材可供拼接")

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

    if text_clips:
        try:
            from src.processing.ffmpeg import composite_subtitles
            ass_path = str(Path(temp_dir).parent / f"subs_{gen.id}.ass")
            _write_ass(text_clips, fps, ass_path, canvas_w=target_w or 1920, canvas_h=target_h or 1080)
            output = composite_subtitles(output, ass_path)
            try:
                Path(ass_path).unlink(missing_ok=True)
            except Exception:
                pass
        except Exception as e:
            logger.warning("字幕压制失败（不影响生成）: %s", e)

    show_subtitles = clip_data.get("showSubtitles", False)
    if show_subtitles and not text_clips:
        try:
            from src.processing.subtitle import get_timestamps
            from src.processing.ffmpeg import composite_subtitles
            logger.info("无文字轨道，开始自动提取字幕（ASR）...")
            segments = get_timestamps(output, language="zh")
            if segments:
                ass_path = str(Path(temp_dir).parent / f"asr_subs_{gen.id}.ass")
                _write_asr_ass(segments, ass_path, canvas_w=target_w or 1920, canvas_h=target_h or 1080)
                output = composite_subtitles(output, ass_path)
                try:
                    Path(ass_path).unlink(missing_ok=True)
                except Exception:
                    pass
                logger.info("ASR 字幕压制完成，共 %d 条", len(segments))
            else:
                logger.warning("ASR 未提取到字幕内容")
        except Exception as e:
            logger.warning("自动字幕提取失败（不影响生成）: %s", e)

    gen.status = "completed"
    gen.output_filepath = output
    gen.thumbnail = generate_thumbnail(output)
    db.commit()
    return gen


def generate_video(db: Session, gen_id: int, voice: str | None = None) -> dict:
    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise fail_response(status_code=404, message="混剪视频不存在")
    return _gen_to_dict(_execute_generate(gen, db, voice))


def dub_generated_video(db: Session, gen_id: int, data: GenDubRequest) -> dict:
    from src.services.tts import dub_from_text

    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise fail_response(status_code=404, message="混剪视频不存在")
    if not gen.output_filepath or not Path(gen.output_filepath).exists():
        raise fail_response(status_code=400, message="请先生成视频")
    if not gen.script:
        raise fail_response(status_code=400, message="没有配音文本")

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
        raise fail_response(status_code=500, message=f"配音失败: {e}")


def batch_generate_groups(db: Session, gen_id: int) -> dict:
    import itertools
    import subprocess
    from src.processing.ffmpeg import FFMPEG, FFPROBE, get_video_duration

    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise fail_response(status_code=404, message="混剪视频不存在")

    try:
        clip_data = json.loads(gen.data) if gen.data else {}
    except Exception:
        clip_data = {}
    tracks = clip_data.get("tracks", [])

    group_tracks = [t for t in tracks if t.get("type") == "group" and t.get("groups")]
    if not group_tracks:
        return _gen_to_dict(_execute_generate(gen, db))

    non_group_tracks = [t for t in tracks if t.get("type") != "group"]

    fps = gen.frame_rate or 30
    target_w = gen.frame_width or None
    target_h = gen.frame_height or None

    groups_order = []
    group_origins = []
    for gt_idx, gt in enumerate(group_tracks):
        clip_map = {c["id"]: c for c in gt.get("list", [])}
        for g_idx, g in enumerate(gt.get("groups", [])):
            videos = g.get("groupVideos", []) or []
            audios = g.get("groupAudios", []) or []
            if not videos:
                continue
            pairs = []
            for vid in videos:
                vclip = clip_map.get(vid)
                if not vclip:
                    continue
                if audios:
                    for aid in audios:
                        aclip = clip_map.get(aid)
                        pairs.append((vclip, aclip))
                else:
                    pairs.append((vclip, None))
            if pairs:
                groups_order.append(pairs)
                group_origins.append((gt_idx, g_idx))

    if not groups_order:
        raise fail_response(status_code=400, message="组内没有可用的视频素材")

    combinations = list(itertools.product(*groups_order))
    seen = set()
    unique_combos = []
    for combo in combinations:
        key = tuple((v.get("id"), a.get("id") if a else None) for v, a in combo)
        if key not in seen:
            seen.add(key)
            unique_combos.append(combo)
    dup_count = len(combinations) - len(unique_combos)
    combinations = unique_combos
    logger.info("组素材批量生成: %d 组, %d 种组合%s",
                len(groups_order), len(combinations),
                f"（去重 {dup_count} 个）" if dup_count else "")

    temp_dir = ensure_date_dir(get_config("mixed_dir"), "segments")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)

    results = []

    # Pre-compute non-group segments (shared across all combinations)
    shared_segment_paths = []
    shared_audio_paths = []
    shared_text_clips = []
    for track in non_group_tracks:
        for clip in track.get("list", []):
            ctype = clip.get("type", "")
            if ctype == "text":
                shared_text_clips.append(clip)
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
                shared_audio_paths.append(fp)
                continue
            seg = _make_segment(clip, fp, fps, gen_id, str(temp_dir))
            if seg:
                shared_segment_paths.append(seg)

    for combo_idx, combo in enumerate(combinations):
        segment_paths = list(shared_segment_paths)
        audio_paths = list(shared_audio_paths)
        text_clips = shared_text_clips

        group_segments = []
        for vclip, aclip in combo:
            fp_v = vclip.get("filepath", "")
            if not fp_v or not Path(fp_v).exists():
                mid = vclip.get("material_id")
                if mid is not None:
                    m = db.query(Material).get(mid)
                    if m and Path(m.filepath).exists():
                        fp_v = m.filepath
            if not fp_v or not Path(fp_v).exists():
                continue

            vid_seg = _make_segment(vclip, fp_v, fps, gen_id, str(temp_dir))
            if not vid_seg:
                continue

            if aclip:
                from src.processing.ffmpeg import mix_audio_tracks
                fp_a = aclip.get("filepath", "")
                if not fp_a or not Path(fp_a).exists():
                    mid = aclip.get("material_id")
                    if mid is not None:
                        m = db.query(Material).get(mid)
                        if m and Path(m.filepath).exists():
                            fp_a = m.filepath
                if fp_a and Path(fp_a).exists():
                    vid_dur = (vclip.get("end", 0) - vclip.get("start", 0)) / fps
                    audio_seg = _extract_audio_segment(fp_a, vid_dur, gen_id, temp_dir)
                    if audio_seg:
                        try:
                            vid_seg = mix_audio_tracks(vid_seg, [audio_seg])
                            try:
                                Path(audio_seg).unlink(missing_ok=True)
                            except Exception:
                                pass
                        except Exception as e:
                            logger.warning("组内音频混入失败: %s", e)

            group_segments.append(vid_seg)

        if not group_segments:
            logger.warning("组合 %d 没有可用视频素材，跳过", combo_idx + 1)
            continue

        all_segments = segment_paths + group_segments

        suffix = f"_{combo_idx + 1}" if len(combinations) > 1 else ""
        output = str(ensure_date_dir(get_config("mixed_dir"), f"remix_{gen_id}_g{suffix}.mp4"))

        ass_path = None
        if text_clips:
            ass_path = str(Path(temp_dir).parent / f"subs_{gen_id}_g{combo_idx}.ass")
            _write_ass(text_clips, fps, ass_path, canvas_w=target_w or 1920, canvas_h=target_h or 1080)

        try:
            from src.processing.ffmpeg import concat_with_audio_and_subs
            output = concat_with_audio_and_subs(
                all_segments, output,
                audio_paths=audio_paths if audio_paths else None,
                ass_path=ass_path,
                target_width=target_w,
                target_height=target_h,
            )
        except Exception as e:
            logger.warning("拼接+混音+字幕合并失败: %s", e)
            continue

        try:
            if ass_path:
                Path(ass_path).unlink(missing_ok=True)
        except Exception:
            pass

        for sp in group_segments:
            try:
                if sp.startswith(str(temp_dir)):
                    Path(sp).unlink(missing_ok=True)
            except Exception:
                pass

        show_subtitles = clip_data.get("showSubtitles", False)
        if show_subtitles and not text_clips:
            try:
                from src.processing.ffmpeg import composite_subtitles, extract_audio
                from src.processing.asr import transcribe
                logger.info("批量生成直接走 ASR 提取字幕...")
                audio_path = extract_audio(output)
                segments = transcribe(audio_path, language="zh")
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except Exception:
                    pass
                if segments:
                    ass_path = str(Path(temp_dir).parent / f"asr_subs_{gen_id}_g{combo_idx}.ass")
                    _write_asr_ass(segments, ass_path, canvas_w=target_w or 1920, canvas_h=target_h or 1080)
                    output = composite_subtitles(output, ass_path)
                    try:
                        Path(ass_path).unlink(missing_ok=True)
                    except Exception:
                        pass
                    logger.info("ASR 字幕压制完成，共 %d 条", len(segments))
                else:
                    logger.warning("ASR 未提取到字幕内容")
            except Exception as e:
                logger.warning("自动字幕提取失败（不影响生成）: %s", e)

        thumb = generate_thumbnail(output)

        reconstructed_tracks = list(non_group_tracks)
        resolved_gt = {}
        for i, (vclip, aclip) in enumerate(combo):
            gt_idx, g_idx = group_origins[i]
            if gt_idx not in resolved_gt:
                gt = group_tracks[gt_idx]
                resolved_gt[gt_idx] = {
                    "type": gt.get("type", "group"),
                    "list": [],
                    "groups": [],
                }
            entry = resolved_gt[gt_idx]
            existing_ids = {c["id"] for c in entry["list"]}
            if vclip["id"] not in existing_ids:
                entry["list"].append(vclip)
                existing_ids.add(vclip["id"])
            if aclip and aclip["id"] not in existing_ids:
                entry["list"].append(aclip)
            group_entry = {"groupVideos": [vclip["id"]], "groupAudios": [aclip["id"]] if aclip else []}
            entry["groups"].append(group_entry)
        for gt_idx in sorted(resolved_gt.keys()):
            reconstructed_tracks.append(resolved_gt[gt_idx])
        reconstructed_data = json.dumps({"tracks": reconstructed_tracks})

        combo_gen = GeneratedVideo(
            title=f"{gen.title or '混剪'}{suffix}",
            script=gen.script,
            data=reconstructed_data,
            output_filepath=output,
            duration=get_video_duration(output) or 0.0,
            frame_width=gen.frame_width,
            frame_height=gen.frame_height,
            frame_rate=gen.frame_rate,
            status="completed",
            thumbnail=thumb,
            folder_id=gen.folder_id,
        )
        db.add(combo_gen)
        db.commit()
        db.refresh(combo_gen)
        results.append(_gen_to_dict(combo_gen))

    # Cleanup shared segments
    for sp in shared_segment_paths:
        try:
            if sp.startswith(str(temp_dir)):
                Path(sp).unlink(missing_ok=True)
        except Exception:
            pass

    if not results:
        raise fail_response(status_code=400, message="没有成功生成任何视频")

    return {"count": len(results), "results": results}


def batch_generate_groups_stream(db: Session, gen_id: int):
    """SSE 流式版本：逐条生成并实时推送进度"""
    import itertools
    import subprocess
    from src.processing.ffmpeg import FFMPEG, FFPROBE, get_video_duration

    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        yield _sse_event("error", {"message": "混剪视频不存在"})
        return

    try:
        clip_data = json.loads(gen.data) if gen.data else {}
    except Exception:
        clip_data = {}
    tracks = clip_data.get("tracks", [])

    group_tracks = [t for t in tracks if t.get("type") == "group" and t.get("groups")]
    if not group_tracks:
        # 无组轨道：走普通生成，直接返回一条结果
        try:
            result = _gen_to_dict(_execute_generate(gen, db))
            yield _sse_event("progress", {"current": 1, "total": 1, "video": result})
            yield _sse_event("complete", {"count": 1, "results": [result]})
        except HTTPException as e:
            yield _sse_event("error", {"message": str(e.detail)})
        except Exception as e:
            yield _sse_event("error", {"message": str(e)})
        return

    non_group_tracks = [t for t in tracks if t.get("type") != "group"]

    fps = gen.frame_rate or 30
    target_w = gen.frame_width or None
    target_h = gen.frame_height or None

    groups_order = []
    group_origins = []
    for gt_idx, gt in enumerate(group_tracks):
        clip_map = {c["id"]: c for c in gt.get("list", [])}
        for g_idx, g in enumerate(gt.get("groups", [])):
            videos = g.get("groupVideos", []) or []
            audios = g.get("groupAudios", []) or []
            if not videos:
                continue
            pairs = []
            for vid in videos:
                vclip = clip_map.get(vid)
                if not vclip:
                    continue
                if audios:
                    for aid in audios:
                        aclip = clip_map.get(aid)
                        pairs.append((vclip, aclip))
                else:
                    pairs.append((vclip, None))
            if pairs:
                groups_order.append(pairs)
                group_origins.append((gt_idx, g_idx))

    if not groups_order:
        yield _sse_event("error", {"message": "组内没有可用的视频素材"})
        return

    combinations = list(itertools.product(*groups_order))
    seen = set()
    unique_combos = []
    for combo in combinations:
        key = tuple((v.get("id"), a.get("id") if a else None) for v, a in combo)
        if key not in seen:
            seen.add(key)
            unique_combos.append(combo)
    combinations = unique_combos
    total = len(combinations)
    logger.info("组素材批量生成(SSE): %d 组, %d 种组合", len(groups_order), total)

    temp_dir = ensure_date_dir(get_config("mixed_dir"), "segments")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)

    results = []

    # Pre-compute non-group segments (shared across all combinations)
    shared_segment_paths = []
    shared_audio_paths = []
    shared_text_clips = []
    for track in non_group_tracks:
        for clip in track.get("list", []):
            ctype = clip.get("type", "")
            if ctype == "text":
                shared_text_clips.append(clip)
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
                shared_audio_paths.append(fp)
                continue
            seg = _make_segment(clip, fp, fps, gen_id, str(temp_dir))
            if seg:
                shared_segment_paths.append(seg)

    for combo_idx, combo in enumerate(combinations):
        segment_paths = list(shared_segment_paths)
        audio_paths = list(shared_audio_paths)
        text_clips = shared_text_clips

        group_segments = []
        for vclip, aclip in combo:
            fp_v = vclip.get("filepath", "")
            if not fp_v or not Path(fp_v).exists():
                mid = vclip.get("material_id")
                if mid is not None:
                    m = db.query(Material).get(mid)
                    if m and Path(m.filepath).exists():
                        fp_v = m.filepath
            if not fp_v or not Path(fp_v).exists():
                continue

            vid_seg = _make_segment(vclip, fp_v, fps, gen_id, str(temp_dir))
            if not vid_seg:
                continue

            if aclip:
                from src.processing.ffmpeg import mix_audio_tracks
                fp_a = aclip.get("filepath", "")
                if not fp_a or not Path(fp_a).exists():
                    mid = aclip.get("material_id")
                    if mid is not None:
                        m = db.query(Material).get(mid)
                        if m and Path(m.filepath).exists():
                            fp_a = m.filepath
                if fp_a and Path(fp_a).exists():
                    vid_dur = (vclip.get("end", 0) - vclip.get("start", 0)) / fps
                    audio_seg = _extract_audio_segment(fp_a, vid_dur, gen_id, temp_dir)
                    if audio_seg:
                        try:
                            vid_seg = mix_audio_tracks(vid_seg, [audio_seg])
                            try:
                                Path(audio_seg).unlink(missing_ok=True)
                            except Exception:
                                pass
                        except Exception as e:
                            logger.warning("组内音频混入失败: %s", e)

            group_segments.append(vid_seg)

        if not group_segments:
            logger.warning("组合 %d 没有可用视频素材，跳过", combo_idx + 1)
            continue

        all_segments = segment_paths + group_segments

        suffix = f"_{combo_idx + 1}" if len(combinations) > 1 else ""
        output = str(ensure_date_dir(get_config("mixed_dir"), f"remix_{gen_id}_g{suffix}.mp4"))

        ass_path = None
        if text_clips:
            ass_path = str(Path(temp_dir).parent / f"subs_{gen_id}_g{combo_idx}.ass")
            _write_ass(text_clips, fps, ass_path, canvas_w=target_w or 1920, canvas_h=target_h or 1080)

        try:
            from src.processing.ffmpeg import concat_with_audio_and_subs
            output = concat_with_audio_and_subs(
                all_segments, output,
                audio_paths=audio_paths if audio_paths else None,
                ass_path=ass_path,
                target_width=target_w,
                target_height=target_h,
            )
        except Exception as e:
            logger.warning("拼接+混音+字幕合并失败: %s", e)
            continue

        try:
            if ass_path:
                Path(ass_path).unlink(missing_ok=True)
        except Exception:
            pass

        for sp in group_segments:
            try:
                if sp.startswith(str(temp_dir)):
                    Path(sp).unlink(missing_ok=True)
            except Exception:
                pass

        show_subtitles = clip_data.get("showSubtitles", False)
        if show_subtitles and not text_clips:
            try:
                from src.processing.ffmpeg import composite_subtitles, extract_audio
                from src.processing.asr import transcribe
                logger.info("批量生成直接走 ASR 提取字幕...")
                audio_path = extract_audio(output)
                segments = transcribe(audio_path, language="zh")
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except Exception:
                    pass
                if segments:
                    ass_path = str(Path(temp_dir).parent / f"asr_subs_{gen_id}_g{combo_idx}.ass")
                    _write_asr_ass(segments, ass_path, canvas_w=target_w or 1920, canvas_h=target_h or 1080)
                    output = composite_subtitles(output, ass_path)
                    try:
                        Path(ass_path).unlink(missing_ok=True)
                    except Exception:
                        pass
                    logger.info("ASR 字幕压制完成，共 %d 条", len(segments))
                else:
                    logger.warning("ASR 未提取到字幕内容")
            except Exception as e:
                logger.warning("自动字幕提取失败（不影响生成）: %s", e)

        thumb = generate_thumbnail(output)

        reconstructed_tracks = list(non_group_tracks)
        resolved_gt = {}
        for i, (vclip, aclip) in enumerate(combo):
            gt_idx, g_idx = group_origins[i]
            if gt_idx not in resolved_gt:
                gt = group_tracks[gt_idx]
                resolved_gt[gt_idx] = {
                    "type": gt.get("type", "group"),
                    "list": [],
                    "groups": [],
                }
            entry = resolved_gt[gt_idx]
            existing_ids = {c["id"] for c in entry["list"]}
            if vclip["id"] not in existing_ids:
                entry["list"].append(vclip)
                existing_ids.add(vclip["id"])
            if aclip and aclip["id"] not in existing_ids:
                entry["list"].append(aclip)
            group_entry = {"groupVideos": [vclip["id"]], "groupAudios": [aclip["id"]] if aclip else []}
            entry["groups"].append(group_entry)
        for gt_idx in sorted(resolved_gt.keys()):
            reconstructed_tracks.append(resolved_gt[gt_idx])
        reconstructed_data = json.dumps({"tracks": reconstructed_tracks})

        combo_gen = GeneratedVideo(
            title=f"{gen.title or '混剪'}{suffix}",
            script=gen.script,
            data=reconstructed_data,
            output_filepath=output,
            duration=get_video_duration(output) or 0.0,
            frame_width=gen.frame_width,
            frame_height=gen.frame_height,
            frame_rate=gen.frame_rate,
            status="completed",
            thumbnail=thumb,
            folder_id=gen.folder_id,
        )
        db.add(combo_gen)
        db.commit()
        db.refresh(combo_gen)
        result = _gen_to_dict(combo_gen)
        results.append(result)

        yield _sse_event("progress", {"current": combo_idx + 1, "total": total, "video": result})

    # Cleanup shared segments
    for sp in shared_segment_paths:
        try:
            if sp.startswith(str(temp_dir)):
                Path(sp).unlink(missing_ok=True)
        except Exception:
            pass

    if not results:
        yield _sse_event("error", {"message": "没有成功生成任何视频"})
    else:
        yield _sse_event("complete", {"count": len(results), "results": results})


def auto_batch_generate_stream(data: AutoBatchGenerateRequest, db: Session):
    """SSE 流式版本：逐条自动生成并实时推送进度"""
    count = max(1, min(data.count, 50))

    results = []
    for i in range(count):
        try:
            result = _execute_auto_generate(data, db, batch_index=i)
            results.append(result)
            yield _sse_event("progress", {"current": i + 1, "total": count, "video": result})
        except HTTPException as e:
            yield _sse_event("error", {"message": str(e.detail)})
            return
        except Exception as e:
            logger.warning("第 %d 条生成失败: %s", i + 1, e)

    if not results:
        yield _sse_event("error", {"message": "没有成功生成任何视频"})
    else:
        yield _sse_event("complete", {"count": len(results), "results": results})


def _sse_event(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"
