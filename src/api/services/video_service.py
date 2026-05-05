"""Video business logic: CRUD, upload, download, split, dub, ASR handling."""
import re
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.api.schemas import (
    ParagraphItem,
    SmartExtractAudioOut,
    SmartSubtitlesOut,
    SplitAnalyzeOut,
    SplitCutOut,
    VideoDownloadRequest,
    VideoOut,
    VideoSplitOut,
    VideoStatusOut,
)
from src.config import get_config
from src.db.models import Video
from src.logger import default_logger as logger
from src.pipelines import download
from src.processing.asr import transcribe_return_text
from src.processing.ffmpeg import get_video_duration, get_video_metadata, extract_audio
from src.processing.paragraph import merge_into_paragraphs
from src.processing.subtitle import get_timestamps
from src.utils import ensure_date_dir, generate_thumbnail, thumb_url


def _video_to_dict(v: Video) -> dict:
    d = VideoOut.model_validate(v).model_dump(mode="json")
    d["thumbnail"] = thumb_url(d.get("thumbnail", ""))
    return d


def list_videos(
    db: Session,
    q: str | None = None,
    folder_id: int | None = None,
    skip: int = 0,
    limit: int = 20,
) -> dict:
    query = db.query(Video).order_by(Video.id.desc())
    if q:
        query = query.filter(Video.filename.contains(q))
    if folder_id is not None:
        if folder_id == 0:
            query = query.filter(Video.folder_id.is_(None))
        else:
            query = query.filter(Video.folder_id == folder_id)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"items": [_video_to_dict(v) for v in items], "total": total}


def get_video(db: Session, video_id: int) -> Video:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    return v


def update_video(db: Session, video_id: int, filename: str | None, content: str | None) -> dict:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if filename is not None:
        v.filename = filename
    if content is not None:
        v.content = content
    db.commit()
    db.refresh(v)
    return _video_to_dict(v)


def dub_video_service(db: Session, video_id: int, voice: str | None) -> dict:
    from src.services.tts import dub_from_text

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not v.filepath or not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")
    if not v.content:
        raise fail_response(status_code=400, message="视频没有文案内容，请先保存文案")

    try:
        output_path = str(ensure_date_dir(
            get_config("mixed_dir"), f"dub_{video_id}_{Path(v.filepath).stem}.mp4"))
        result = dub_from_text(v.filepath, v.content, voice=voice, output_path=output_path)
        v.filepath = result
        db.commit()
        db.refresh(v)
        return _video_to_dict(v)
    except Exception as e:
        raise fail_response(status_code=500, message=f"配音失败: {e}")


def upload_video(
    db: Session,
    file,
    language: str = "zh",
    folder_id: int | None = None,
    extract_text: bool = True,
) -> dict:
    logger.info("参数信息: {} {}".format(folder_id, extract_text))
    ext = Path(file.filename).suffix if file.filename else ".mp4"
    filename = file.filename or f"{uuid.uuid4().hex}{ext}"

    dest = ensure_date_dir(get_config("source_dir"), filename)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    filepath = str(dest)
    duration = get_video_duration(filepath)
    meta = get_video_metadata(filepath)

    logger.info("获取视频元数据信息{} {}".format(meta, folder_id))
    v = Video(
        filename=filename,
        filepath=filepath,
        duration=duration,
        frame_width=meta.get("frame_width", 0),
        frame_height=meta.get("frame_height", 0),
        frame_rate=meta.get("frame_rate", 0.0),
        status="completed",
        folder_id=folder_id,
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    v.thumbnail = generate_thumbnail(filepath)
    if v.thumbnail:
        db.commit()
        db.refresh(v)

    content = ""
    if extract_text:
        try:
            try:
                audio_path = extract_audio(filepath)
                content = transcribe_return_text(audio_path, language=language)
            except Exception as e:
                logger.error(f"ASR 提取语音失败:{e}")
        except Exception as e:
            logger.error("ASR 处理失败: %s", e)

    v2 = db.query(Video).get(v.id)
    if v2:
        v2.status = "completed"
        v2.content = content
        db.commit()
        db.refresh(v2)

    return _video_to_dict(v2 or v)


async def download_video_service(db: Session, data: VideoDownloadRequest) -> dict:
    logger.info("请求信息: %s", data)
    query_text = data.urls.strip()
    if not query_text:
        raise fail_response(status_code=400, message="请提供视频地址或分享内容")

    url_match = re.search(r'https?://[^\s,，。；！？、""''【】《》<>^`{|}]+', query_text)
    if url_match:
        extracted = url_match.group(0)
        logger.info("从分享内容提取到 URL: %s", extracted)
        query_text = extracted

    dest = ensure_date_dir(get_config("source_dir"), "tmp.mp4")
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("待下载视频目录: %s", dest.parent)
    video_info, filepath = await download.process_download(query_text, dest.parent, data.proxy or None)
    logger.info("视频已下载: %s", filepath)
    duration = get_video_duration(str(filepath))
    meta = get_video_metadata(str(filepath))

    logger.info("视频元数据: %s", meta)
    v = Video(
        filename=str(video_info.title),
        filepath=str(filepath),
        duration=duration,
        frame_width=meta.get("frame_width", 0),
        frame_height=meta.get("frame_height", 0),
        frame_rate=meta.get("frame_rate", 0.0),
        status="completed",
        thumbnail=generate_thumbnail(str(filepath)),
        folder_id=data.folder_id,
    )

    content = ""
    if data.extract_text:
        try:
            try:
                audio_path = extract_audio(str(filepath))
                content = transcribe_return_text(audio_path)
            except Exception as e:
                logger.error(f"ASR 提取语音失败:{e}")
        except Exception as e:
            logger.error("ASR 处理失败: %s", e)

    v.status = "completed"
    v.content = content
    db.add(v)
    db.commit()
    db.refresh(v)

    return _video_to_dict(v)


def get_video_file_path(db: Session, video_id: int) -> str:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not v.filepath or not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="文件不存在")
    return v.filepath


def get_video_status(db: Session, video_id: int) -> VideoStatusOut:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    return VideoStatusOut(id=v.id, status=v.status, content=v.content, filename=v.filename)


def delete_video(db: Session, video_id: int) -> dict:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if v.filepath and Path(v.filepath).exists():
        Path(v.filepath).unlink(missing_ok=True)
    db.delete(v)
    db.commit()
    return {"ok": True}


def split_analyze(db: Session, video_id: int, language: str = "zh") -> SplitAnalyzeOut:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    timestamps = get_timestamps(v.filepath, language=language)
    if not timestamps:
        raise fail_response(status_code=400, message="未能提取到时间轴信息")

    paragraphs = merge_into_paragraphs(timestamps)

    items = [
        ParagraphItem(seq_index=p["seq_index"], start=p["start"], end=p["end"], text=p["text"])
        for p in paragraphs
    ]
    return SplitAnalyzeOut(
        paragraphs=items,
        total_duration=v.duration,
    )


def smart_split_subtitles(db: Session, video_id: int) -> dict:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    from src.processing.subtitle import extract_soft_subtitles

    try:
        subtitles = extract_soft_subtitles(v.filepath)
    except Exception as e:
        logger.warning("  → 软字幕提取失败: %s", e)
        subtitles = None
    count = len(subtitles) if subtitles else 0
    msg = f"提取到 {count} 个字幕片段" if count > 0 else "未找到软字幕"
    return {
        "data": SmartSubtitlesOut(subtitles=subtitles, segment_count=count).model_dump(mode="json"),
        "message": msg,
    }


def smart_split_extract_audio(db: Session, video_id: int) -> dict:
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    try:
        audio_path = extract_audio(v.filepath)
    except Exception as e:
        raise fail_response(status_code=500, message=f"音频提取失败: {e}")

    return {
        "data": SmartExtractAudioOut(audio_path=audio_path).model_dump(mode="json"),
        "message": "音频提取完成",
    }


def smart_split_analyze(db: Session, video_id: int, audio_path: str, language: str, subtitles: list[dict] | None) -> dict:
    import os
    from src.processing.asr import transcribe
    from src.config import BASE_DIR

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")

    bin_dir = str(BASE_DIR + "/bin")
    prev_path = os.environ.get("PATH", "")
    os.environ["PATH"] = bin_dir + os.pathsep + prev_path
    try:
        logger.info("  → 开始 ASR 语音识别...")
        asr_segments = transcribe(audio_path, language=language)
    except Exception as e:
        raise fail_response(status_code=500, message=f"语音识别失败: {e}")
    finally:
        os.environ["PATH"] = prev_path

    if not asr_segments:
        raise fail_response(status_code=400, message="ASR 转录未产生任何片段")

    logger.info("  → ASR 完成，共 %d 个片段", len(asr_segments))

    if subtitles and len(subtitles) > 0:
        source_segments = subtitles
        logger.info("  → 使用软字幕进行段落合并（%d 个片段）", len(source_segments))
    else:
        source_segments = asr_segments
        logger.info("  → 回退到 ASR 片段进行段落合并（%d 个片段）", len(source_segments))

    paragraphs = merge_into_paragraphs(source_segments)

    items = [
        ParagraphItem(seq_index=p["seq_index"], start=p["start"], end=p["end"], text=p["text"])
        for p in paragraphs
    ]
    return {
        "data": SplitAnalyzeOut(paragraphs=items, total_duration=v.duration).model_dump(mode="json"),
        "message": f"分析完成，共 {len(items)} 个自然段落",
    }


def split_cut(db: Session, video_id: int, paragraphs: list, extract_text: bool, remove_audio: bool) -> dict:
    import subprocess
    from src.processing.ffmpeg import split_video_clip
    from src.db.models import Material as MaterialModel
    from src.config import BASE_DIR
    from src.api.schemas import MaterialOut

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    ffmpeg_cmd = f"{BASE_DIR}/bin/ffmpeg"

    materials = []
    material_ids = []
    seg_audio = ""
    for p in paragraphs:
        seg_path = ensure_date_dir(get_config("material_dir"), f"seg_{video_id}_{p.seq_index}.mp4")
        seg_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            split_video_clip(
                video_path=v.filepath,
                vocals_path="",
                start=p.start,
                end=p.end,
                output_path=str(seg_path),
                no_audio=remove_audio,
            )
        except Exception:
            continue

        text = p.text or ""
        if extract_text and not text.strip():
            try:
                seg_audio = str(ensure_date_dir(
                    get_config("material_dir"), f"seg_audio_{video_id}_{p.seq_index}.wav"))
                subprocess.run([
                    ffmpeg_cmd, "-ss", str(p.start), "-to", str(p.end),
                    "-i", str(v.filepath),
                    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                    "-y", seg_audio,
                ], check=True, capture_output=True)
                text = transcribe_return_text(seg_audio)
            except Exception:
                text = ""
            finally:
                if seg_audio:
                    Path(seg_audio).unlink(missing_ok=True)

        mat_filename = p.title or seg_path.name
        mat = MaterialModel(
            type="video",
            content=text,
            start_time=p.start,
            end_time=p.end,
            frame_width=v.frame_width,
            frame_height=v.frame_height,
            frame_rate=v.frame_rate,
            filename=mat_filename,
            filepath=str(seg_path),
            thumbnail=generate_thumbnail(str(seg_path)),
        )
        db.add(mat)
        db.flush()
        material_ids.append(mat.id)
        materials.append(MaterialOut.model_validate(mat).model_dump(mode="json"))

        if text:
            try:
                from src.db.vector import VectorStore
                VectorStore().add_material(mat.id, text, {
                    "type": mat.type,
                    "start_time": mat.start_time,
                    "end_time": mat.end_time,
                    "frame_width": mat.frame_width,
                    "frame_height": mat.frame_height,
                    "frame_rate": mat.frame_rate,
                    "filename": mat.filename or "",
                    "filepath": mat.filepath or "",
                })
            except Exception:
                pass

    db.commit()
    return SplitCutOut(
        material_count=len(material_ids),
        material_ids=material_ids,
        materials=materials,
    )


def split_video_full(db: Session, video_id: int, language: str = "zh") -> dict:
    from src.processing.ffmpeg import split_video_clip
    from src.db.models import Material as MaterialModel

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    timestamps = get_timestamps(v.filepath, language=language)
    if not timestamps:
        raise fail_response(status_code=400, message="未能提取到时间轴信息")

    paragraphs = merge_into_paragraphs(timestamps)

    material_ids = []
    for p in paragraphs:
        seg_path = ensure_date_dir(get_config("material_dir"), f"seg_{video_id}_{p['seq_index']}.mp4")
        seg_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            split_video_clip(
                video_path=v.filepath,
                vocals_path="",
                start=p["start"],
                end=p["end"],
                output_path=str(seg_path),
                no_audio=True,
            )
        except Exception:
            continue

        mat = MaterialModel(
            type="video",
            content=p["text"],
            start_time=p["start"],
            end_time=p["end"],
            frame_width=v.frame_width,
            frame_height=v.frame_height,
            frame_rate=v.frame_rate,
            filename=seg_path.name,
            filepath=str(seg_path),
            thumbnail=generate_thumbnail(str(seg_path)),
        )
        db.add(mat)
        db.flush()
        material_ids.append(mat.id)

        if p["text"]:
            try:
                from src.db.vector import VectorStore
                VectorStore().add_material(mat.id, p["text"], {
                    "type": mat.type,
                    "start_time": mat.start_time,
                    "end_time": mat.end_time,
                    "frame_width": mat.frame_width,
                    "frame_height": mat.frame_height,
                    "frame_rate": mat.frame_rate,
                    "filename": mat.filename or "",
                    "filepath": mat.filepath or "",
                })
            except Exception:
                pass

    db.commit()
    return VideoSplitOut(material_count=len(material_ids), material_ids=material_ids)


def save_video_to_notes(db: Session, video_id: int) -> dict:
    from src.db.models import Note as NoteModel
    from src.services.agents import call_agent
    from src.api.schemas import NoteOut

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not v.content:
        raise fail_response(status_code=400, message="视频暂无文案")

    formatted = call_agent("note_ast", v.content, max_tokens=4000)

    folder = db.query(NoteModel).filter(
        NoteModel.is_system == True,
        NoteModel.tp == "folder",
    ).first()

    note = NoteModel(
        title=v.filename or f"视频 #{video_id} 笔记",
        content=formatted,
        parent_id=folder.id if folder else None,
        tp="note",
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    return NoteOut.model_validate(note).model_dump(mode="json")
