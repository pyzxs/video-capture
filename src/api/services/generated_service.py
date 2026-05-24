"""Generated video business logic: CRUD, auto-generate, batch, groups, ASS helpers."""
import hashlib
import json
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

from src.utils import ensure_date_dir, generate_thumbnail, thumb_url


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
        asr_fs = max(28, min(72, int(canvas_h / 20)))
        f.write(f"Style: Default,Noto Sans SC,{asr_fs},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
                 "0,0,0,0,100,100,0,0,1,0.8,0,2,10,10,20,1\n\n")
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for start_sec, end_sec, text in entries:
            start_ts = _format_ass_time(start_sec)
            end_ts = _format_ass_time(end_sec)
            f.write(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{text}\n")


def _split_asr_segments(segments: list[dict], fps: float, target_h: int) -> list[dict]:
    """Split ASR segments into subtitle TextClip dicts by sentence boundaries.

    Splitting strategy:
    1. Split at sentence-ending punctuation (。！？!?)
    2. If a sentence is still too long (>18 chars), split further at commas / semicolons
    3. Time is distributed proportionally to character count, with a min of 1.0 s per clip
    """
    import re
    sub_fs = max(28, min(72, int(target_h / 20)))
    MAX_CHARS = 18
    MIN_DUR = 1.0

    def _make_clip(content, cs, ce):
        return {
            "id": f"c-{uuid.uuid4().hex[:7]}",
            "type": "text", "content": content.strip(),
            "start": round(cs * fps),
            "end": round(ce * fps),
            "frameCount": round((ce - cs) * fps),
            "offsetL": 0, "offsetR": 0,
            "centerX": 50, "centerY": 90, "scale": 100,
            "fontSize": sub_fs, "fontFamily": "Noto Sans SC",
            "fontColor": "#ffffff", "bold": False, "italic": False,
            "shadow": False, "outline": False,
        }

    clips = []

    for seg in segments:
        text = (seg.get("text", "") or "").strip()
        start_sec = seg.get("start", 0) or 0
        end_sec = seg.get("end", 0) or 0
        if not text or end_sec <= start_sec:
            continue

        duration = end_sec - start_sec

        # 1. Split at sentence boundaries
        raw_parts = re.split(r'(?<=[。！？!?])\s*', text)
        sentences = [p for p in raw_parts if p.strip()]

        # 2. Further split long sentences at commas / semicolons
        parts = []
        for s in sentences:
            if len(s) <= MAX_CHARS or duration <= MIN_DUR:
                parts.append(s)
            else:
                sub = re.split(r'(?<=[，、；,;])\s*', s)
                parts.extend(p for p in sub if p.strip())

        if not parts:
            continue

        # 3. Merge very short adjacent parts that would get too little time
        total_chars = sum(len(p) for p in parts)
        char_rate = duration / max(total_chars, 1)  # seconds per char
        merged = []
        buf = ""
        for p in parts:
            if buf and (len(buf) + len(p) <= MAX_CHARS or len(p) < 4):
                buf += p
            elif buf:
                merged.append(buf)
                buf = p
            else:
                buf = p
        if buf:
            merged.append(buf)

        # 4. Distribute time proportionally
        merged_chars = [len(p) for p in merged]
        total = sum(merged_chars)
        cursor = start_sec
        for i, p in enumerate(merged):
            piece_dur = max(MIN_DUR, merged_chars[i] * char_rate) if total > 0 else duration / len(merged)
            # Don't exceed remaining time
            piece_dur = min(piece_dur, end_sec - cursor)
            if i == len(merged) - 1:
                piece_dur = end_sec - cursor
            cs = cursor
            ce = cursor + piece_dur
            if ce > cs and p.strip():
                clips.append(_make_clip(p, cs, ce))
            cursor = ce

    return clips


def _extract_audio_for_asr(combo_tracks: list[dict], fps: float, output_wav: str) -> str | None:
    """Extract combined audio from combo_tracks for ASR.

    Concatenates all audio clips with their trim offsets and durations,
    outputting a mono 16 kHz WAV.  Returns the path or None.
    """
    from src.processing.ffmpeg import FFMPEG, _run

    audio_track = next((t for t in combo_tracks if t.get("type") == "audio" and t.get("list")), None)
    if not audio_track:
        return None

    clips = audio_track["list"]
    inputs = []
    filter_parts = []
    n = 0
    for c in clips:
        fp = c.get("filepath")
        if not fp or not Path(fp).exists():
            continue
        dur = ((c.get("end", 0) or 0) - (c.get("start", 0) or 0)) / max(fps, 1)
        off = (c.get("offsetL", 0) or 0) / max(fps, 1)
        if dur <= 0.05:
            continue
        inputs.extend(["-i", str(fp)])
        filter_parts.append(f"[{n}:a]atrim=start={off:.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS[a{n}]")
        n += 1

    if n == 0:
        return None

    labels = "".join(f"[a{i}]" for i in range(n))
    filter_str = f"{';'.join(filter_parts)};{labels}concat=n={n}:v=0:a=1[out]"

    cmd = [
        FFMPEG, *inputs,
        "-filter_complex", filter_str,
        "-map", "[out]", "-ac", "1", "-ar", "16000",
        "-y", str(output_wav),
    ]
    _run(cmd, check=True, capture_output=True)
    return str(output_wav)


def _clip_field(clip: dict, camel: str, snake: str = None) -> any:
    """Read clip field with camelCase priority, fallback to snake_case."""
    if camel in clip and clip[camel] is not None:
        return clip[camel]
    if snake and snake in clip and clip[snake] is not None:
        return clip[snake]
    return None


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

            mid = _clip_field(clip, "materialId", "material_id")
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
                clip["materialId"] = mat.id
                clip.pop("material_id", None)
                modified = True

    if modified:
        return json.dumps(data, ensure_ascii=False)
    return data_json


def _validate_timeline_data(data_json: str) -> str | None:
    """Validate timeline data structure. Returns error message or None if valid."""
    if not data_json:
        return None
    try:
        data = json.loads(data_json)
    except (json.JSONDecodeError, TypeError):
        return "data 不是有效的 JSON"

    if not isinstance(data, dict):
        return "data 必须是 JSON 对象"

    tracks = data.get("tracks")
    if tracks is not None and not isinstance(tracks, list):
        return "tracks 必须是数组"

    if isinstance(tracks, list):
        for ti, track in enumerate(tracks):
            if not isinstance(track, dict):
                return f"track[{ti}] 必须是对象"
            tlist = track.get("list")
            if tlist is not None and not isinstance(tlist, list):
                return f"track[{ti}].list 必须是数组"
            if isinstance(tlist, list):
                for ci, clip in enumerate(tlist):
                    if not isinstance(clip, dict):
                        return f"track[{ti}].list[{ci}] 必须是对象"
                    # Required fields for non-text clips
                    if clip.get("type") != "text":
                        if "id" not in clip:
                            return f"track[{ti}].list[{ci}] 缺少 id"
                    start = clip.get("start")
                    end = clip.get("end")
                    if start is not None and end is not None and start >= end:
                        return f"track[{ti}].list[{ci}] start 必须小于 end"

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
    err = _validate_timeline_data(data.data or "{}")
    if err:
        raise fail_response(status_code=400, message=f"时间线数据校验失败: {err}")
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
            err = _validate_timeline_data(value or "{}")
            if err:
                raise fail_response(status_code=400, message=f"时间线数据校验失败: {err}")
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
                    "materialId": m.id,
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

    # 4.6 字幕渲染（基于配音脚本的 TTS 音频做 ASR 获取时间戳）
    if data.show_subtitle and audio_filepath and Path(audio_filepath).exists():
        try:
            from src.processing.asr import transcribe
            from src.processing.ffmpeg import composite_subtitles
            logger.info("  → 开始提取配音字幕...")
            segments = transcribe(audio_filepath, language="zh")
            if segments:
                ass_path = str(Path(final_output).parent / f"{prefix_file}_subs.ass")
                _write_asr_ass(segments, ass_path)
                final_output = composite_subtitles(final_output, ass_path)
                try:
                    Path(ass_path).unlink(missing_ok=True)
                except Exception:
                    pass
                logger.info("  → 配音字幕已压制，共 %d 条", len(segments))
            else:
                logger.warning("  → ASR 未提取到字幕内容")
        except Exception as e:
            logger.warning("  → 字幕渲染失败（不影响生成）: %s", e)

    # 5. 构建轨道数据
    material_list = []
    current_frame = 0
    for r in matched_materials:
        dur = round(((r.get("end_time", 10) - r.get("start_time", 0)) or 10.0) * frame_rate_val)
        dur = max(dur, 30)
        material_list.append({
            "id": f"c-{uuid.uuid4().hex[:7]}",
            "type": r.get("type", "video"),
            "materialId": r["materialId"],
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
                "materialId": tts_material_id,
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
    from src.processing.compositor import composite_tracks

    try:
        clip_data = json.loads(gen.data) if gen.data else {}
    except Exception:
        clip_data = {}
    tracks = clip_data.get("tracks", [])

    fps = gen.frame_rate or 30
    target_w = gen.frame_width or 1920
    target_h = gen.frame_height or 1080

    temp_dir = ensure_date_dir(get_config("mixed_dir"), "segments")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)

    # Collect text clips for ASS subtitle post-processing
    text_clips = []
    for track in tracks:
        for clip in track.get("list", []):
            if clip.get("type") == "text":
                text_clips.append(clip)

    # Resolve missing filepaths from materialId / material_id references
    for track in tracks:
        for clip in track.get("list", []):
            fp = clip.get("filepath", "")
            if not fp or not Path(fp).exists():
                mid = _clip_field(clip, "materialId", "material_id")
                if mid is not None:
                    m = db.query(Material).get(mid)
                    if m and Path(m.filepath).exists():
                        clip["filepath"] = str(Path(m.filepath).resolve())

    # Multi-track compositing (replaces old flat concat pipeline)
    output = str(ensure_date_dir(get_config("mixed_dir"), f"remix_{gen.id}.mp4"))
    composite_tracks(tracks, output, fps, target_w, target_h, str(temp_dir))

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


def _resolve_group_tracks(tracks: list[dict]) -> tuple[list[dict], list[dict], list[tuple[int, int]]]:
    """Parse tracks into (non_group_tracks, group_tracks, groups_order) with origins.

    Each group has one or more videos.  Every video is a separate alternative
    in the Cartesian product — a group with 2 videos contributes 2 items.
    """
    import itertools

    group_tracks = [t for t in tracks if t.get("type") == "group" and t.get("groups")]
    non_group_tracks = [t for t in tracks if t.get("type") != "group"]

    groups_order = []
    group_origins = []
    for gt_idx, gt in enumerate(group_tracks):
        clip_map = {c["id"]: c for c in gt.get("list", [])}
        # Sort groups by cardStart for correct timeline order
        sorted_groups = sorted(
            enumerate(gt.get("groups", [])),
            key=lambda x: (x[1].get("cardStart") or 0),
        )
        for g_idx, g in sorted_groups:
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

    return non_group_tracks, group_tracks, groups_order, group_origins


def _build_combo_tracks(
    non_group_tracks: list[dict],
    combo: list[tuple[dict, dict | None]],
    db: Session,
) -> list[dict]:
    """Build flattened tracks array for one combination.

    Groups play sequentially (concatenation) on one video track + one audio
    track.  Clip positions are re-based contiguously with no gaps.
    """
    combo_tracks = [dict(t) for t in non_group_tracks]

    group_video_clips = []
    group_audio_clips = []
    cursor = 0

    for vclip, aclip in combo:
        vclip = dict(vclip)
        vdur = (vclip.get("end", 0) or 0) - (vclip.get("start", 0) or 0)
        vdur = max(vdur, 1)
        vclip["start"] = cursor
        vclip["end"] = cursor + vdur
        vclip["frameCount"] = vdur
        vclip["offsetL"] = 0
        vclip["offsetR"] = 0
        group_video_clips.append(vclip)

        if aclip:
            aclip = dict(aclip)
            aclip["start"] = cursor
            aclip["end"] = cursor + vdur
            aclip["frameCount"] = vdur
            aclip["offsetL"] = 0
            aclip["offsetR"] = 0
            group_audio_clips.append(aclip)
        # Groups without audio leave a silent gap on the audio track

        cursor += vdur

    if group_video_clips:
        combo_tracks.append({
            "type": "video", "name": "组素材",
            "list": group_video_clips,
            "visible": True, "locked": False, "muted": True,
        })
    if group_audio_clips:
        combo_tracks.append({
            "type": "audio", "name": "组音频",
            "list": group_audio_clips,
            "visible": True, "locked": False, "muted": False,
        })

    # Resolve missing filepaths from materialId
    for track in combo_tracks:
        for clip in track.get("list", []):
            fp = clip.get("filepath", "")
            if not fp or not Path(fp).exists():
                mid = _clip_field(clip, "materialId", "material_id")
                if mid is not None:
                    m = db.query(Material).get(mid)
                    if m and Path(m.filepath).exists():
                        clip["filepath"] = str(Path(m.filepath).resolve())

    # Video track is master: cap audio clips to video max end
    video_max_end = 0
    for track in combo_tracks:
        if track.get("type") == "video":
            for clip in track.get("list", []):
                e = clip.get("end", 0) or 0
                if e > video_max_end:
                    video_max_end = e

    if video_max_end > 0:
        for track in combo_tracks:
            if track.get("type") == "audio":
                for clip in track.get("list", []):
                    if (clip.get("end", 0) or 0) > video_max_end:
                        clip["end"] = video_max_end
                        clip["frameCount"] = max(video_max_end - (clip.get("start", 0) or 0), 1)

    return combo_tracks


def _post_composite_subtitles(
    tracks: list[dict],
    output_path: str,
    fps: float,
    canvas_w: int,
    canvas_h: int,
    gen_id: int,
    show_subtitles: bool = False,
) -> tuple[str, list[dict] | None]:
    """Apply text and/or ASR subtitle overlays after compositing.

    Returns (output_path, asr_segments).  asr_segments is a list of {start, end, text}
    dicts ready to be stored as text clips, or None if no ASR was performed.
    """
    text_clips = []
    for track in tracks:
        for clip in track.get("list", []):
            if clip.get("type") == "text":
                text_clips.append(clip)

    mix_dir = ensure_date_dir(get_config("mixed_dir"), "segments")
    out = output_path
    asr_segments = None

    if text_clips:
        try:
            from src.processing.ffmpeg import composite_subtitles
            ass_path = str(Path(mix_dir).parent / f"subs_{gen_id}_{uuid.uuid4().hex[:8]}.ass")
            _write_ass(text_clips, fps, ass_path, canvas_w=canvas_w, canvas_h=canvas_h)
            out = composite_subtitles(out, ass_path)
            try:
                Path(ass_path).unlink(missing_ok=True)
            except Exception:
                pass
        except Exception as e:
            logger.warning("字幕压制失败: %s", e)

    has_audio = any(
        track.get("type") == "audio" and track.get("list")
        or any(c.get("type") == "audio" for c in (track.get("list") or []))
        for track in tracks
    )
    if show_subtitles and not text_clips and has_audio:
        try:
            from src.processing.ffmpeg import composite_subtitles, extract_audio
            from src.processing.asr import transcribe
            audio_path = extract_audio(out)
            segments = transcribe(audio_path, language="zh")
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass
            if segments:
                asr_segments = segments
                ass_path = str(Path(mix_dir).parent / f"asr_{gen_id}_{uuid.uuid4().hex[:8]}.ass")
                _write_asr_ass(segments, ass_path, canvas_w=canvas_w, canvas_h=canvas_h)
                out = composite_subtitles(out, ass_path)
                try:
                    Path(ass_path).unlink(missing_ok=True)
                except Exception:
                    pass
                logger.info("ASR 字幕压制完成，共 %d 条", len(segments))
        except Exception as e:
            logger.warning("自动字幕提取失败: %s", e)

    return out, asr_segments


def batch_generate_groups(db: Session, gen_id: int) -> dict:
    import itertools
    from src.processing.compositor import composite_tracks
    from src.processing.ffmpeg import get_video_duration

    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        raise fail_response(status_code=404, message="混剪视频不存在")

    try:
        clip_data = json.loads(gen.data) if gen.data else {}
    except Exception:
        clip_data = {}
    tracks = clip_data.get("tracks", [])

    non_group_tracks, group_tracks, groups_order, group_origins = _resolve_group_tracks(tracks)

    if not groups_order:
        return _gen_to_dict(_execute_generate(gen, db))

    combinations = list(itertools.product(*groups_order))
    seen = set()
    unique_combos = []
    for combo in combinations:
        key = tuple((v.get("id"), a.get("id") if a else None) for v, a in combo)
        if key not in seen:
            seen.add(key)
            unique_combos.append(combo)
    combinations = unique_combos
    logger.info("组素材批量生成: %d 组, %d 种组合", len(groups_order), len(combinations))

    temp_dir = ensure_date_dir(get_config("mixed_dir"), "segments")
    Path(temp_dir).mkdir(parents=True, exist_ok=True)

    fps = gen.frame_rate or 30
    target_w = gen.frame_width or 1920
    target_h = gen.frame_height or 1080
    show_subtitles = clip_data.get("showSubtitles", False)

    results = []

    for combo_idx, combo in enumerate(combinations):
        combo_tracks = _build_combo_tracks(non_group_tracks, combo, db)

        suffix = f"_{combo_idx + 1}" if len(combinations) > 1 else ""
        output = str(ensure_date_dir(get_config("mixed_dir"), f"remix_{gen_id}_g{suffix}.mp4"))

        # Pre-compositing ASR: extract audio, transcribe, split into text clips
        if show_subtitles:
            try:
                from src.processing.asr import transcribe
                asr_audio = _extract_audio_for_asr(
                    combo_tracks, fps,
                    str(Path(temp_dir) / f"asr_{gen_id}_{combo_idx}.wav"),
                )
                if asr_audio:
                    segments = transcribe(asr_audio, language="zh")
                    try:
                        Path(asr_audio).unlink(missing_ok=True)
                    except Exception:
                        pass
                    if segments:
                        sub_clips = _split_asr_segments(segments, fps, target_h)
                        if sub_clips:
                            combo_tracks.append({
                                "type": "subtitle", "name": "ASR字幕",
                                "list": sub_clips,
                                "visible": True, "locked": False, "muted": False,
                            })
                            logger.info("ASR 字幕预处理完成: %d 段 → %d 条字幕", len(segments), len(sub_clips))
            except Exception as e:
                logger.warning("ASR 预处理失败 (组合 %d): %s", combo_idx + 1, e)

        try:
            composite_tracks(combo_tracks, output, fps, target_w, target_h, str(temp_dir))
        except Exception as e:
            logger.warning("组合 %d 合成失败: %s", combo_idx + 1, e)
            continue

        output, _ = _post_composite_subtitles(
            combo_tracks, output, fps, target_w, target_h, gen_id,
            False,  # ASR already handled pre-compositing; only burn existing text clips
        )

        thumb = generate_thumbnail(output)

        stored_data = json.dumps({"tracks": combo_tracks, "showSubtitles": show_subtitles})

        combo_gen = GeneratedVideo(
            title=f"{gen.title or '混剪'}{suffix}",
            script=gen.script,
            data=stored_data,
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

    if not results:
        raise fail_response(status_code=400, message="没有成功生成任何视频")

    return {"count": len(results), "results": results}


def _batch_generate_groups_stream(db: Session, gen_id: int):
    """SSE 流式版本：逐条生成并实时推送进度（内部实现）。"""
    import itertools
    from src.processing.compositor import composite_tracks
    from src.processing.ffmpeg import get_video_duration

    gen = db.query(GeneratedVideo).get(gen_id)
    if not gen:
        yield _sse_event("error", {"message": "混剪视频不存在"})
        return

    try:
        clip_data = json.loads(gen.data) if gen.data else {}
    except Exception:
        clip_data = {}
    tracks = clip_data.get("tracks", [])

    non_group_tracks, group_tracks, groups_order, group_origins = _resolve_group_tracks(tracks)

    if not groups_order:
        try:
            result = _gen_to_dict(_execute_generate(gen, db))
            yield _sse_event("progress", {"current": 1, "total": 1, "video": result})
            yield _sse_event("complete", {"count": 1, "results": [result]})
        except HTTPException as e:
            yield _sse_event("error", {"message": str(e.detail)})
        except Exception as e:
            yield _sse_event("error", {"message": str(e)})
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

    fps = gen.frame_rate or 30
    target_w = gen.frame_width or 1920
    target_h = gen.frame_height or 1080
    show_subtitles = clip_data.get("showSubtitles", False)

    results = []

    for combo_idx, combo in enumerate(combinations):
        combo_tracks = _build_combo_tracks(non_group_tracks, combo, db)

        suffix = f"_{combo_idx + 1}" if total > 1 else ""
        output = str(ensure_date_dir(get_config("mixed_dir"), f"remix_{gen_id}_g{suffix}.mp4"))

        # Pre-compositing ASR: extract audio, transcribe, split into text clips
        if show_subtitles:
            try:
                from src.processing.asr import transcribe
                asr_audio = _extract_audio_for_asr(
                    combo_tracks, fps,
                    str(Path(temp_dir) / f"asr_{gen_id}_{combo_idx}.wav"),
                )
                if asr_audio:
                    segments = transcribe(asr_audio, language="zh")
                    try:
                        Path(asr_audio).unlink(missing_ok=True)
                    except Exception:
                        pass
                    if segments:
                        sub_clips = _split_asr_segments(segments, fps, target_h)
                        if sub_clips:
                            combo_tracks.append({
                                "type": "subtitle", "name": "ASR字幕",
                                "list": sub_clips,
                                "visible": True, "locked": False, "muted": False,
                            })
                            logger.info("ASR 字幕预处理完成: %d 段 → %d 条字幕", len(segments), len(sub_clips))
            except Exception as e:
                logger.warning("ASR 预处理失败 (组合 %d): %s", combo_idx + 1, e)

        try:
            composite_tracks(combo_tracks, output, fps, target_w, target_h, str(temp_dir))
        except Exception as e:
            logger.warning("组合 %d 合成失败: %s", combo_idx + 1, e)
            continue

        output, _ = _post_composite_subtitles(
            combo_tracks, output, fps, target_w, target_h, gen_id,
            False,  # ASR already handled pre-compositing; only burn existing text clips
        )

        thumb = generate_thumbnail(output)

        stored_data = json.dumps({"tracks": combo_tracks, "showSubtitles": show_subtitles})

        combo_gen = GeneratedVideo(
            title=f"{gen.title or '混剪'}{suffix}",
            script=gen.script,
            data=stored_data,
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

    if not results:
        yield _sse_event("error", {"message": "没有成功生成任何视频"})
    else:
        yield _sse_event("complete", {"count": len(results), "results": results})


def batch_generate_groups_stream(db: Session, gen_id: int):
    """SSE 流式版本：逐条生成并实时推送进度（带 session 生命周期管理）。"""
    from src.db.engine import get_session

    db = get_session()
    try:
        yield from _batch_generate_groups_stream(db, gen_id)
    finally:
        db.close()


def auto_batch_generate_stream(data: AutoBatchGenerateRequest, db: Session):
    """SSE 流式版本：逐条自动生成并实时推送进度"""
    from src.db.engine import get_session

    db = get_session()
    try:
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
    finally:
        db.close()


def _sse_event(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"
