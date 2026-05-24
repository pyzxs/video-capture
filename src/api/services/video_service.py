"""Video business logic: CRUD, upload, download, split, dub, ASR handling."""
import asyncio
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.api.schemas import (
    ParagraphItem,
    SmartExtractAudioOut,
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
from src.processing.asr import transcribe_return_text, transcribe_by_api
from src.processing.ffmpeg import get_video_info, extract_audio
from src.processing.paragraph import merge_into_paragraphs
from src.processing.subtitle import get_timestamps
from src.utils import ensure_date_dir, generate_thumbnail, thumb_url, _CREATIONFLAGS


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

    # 若 content > 200 字且尚未有 ASR 结果，加入后台队列
    if v.content and len(v.content) > 200 and not v.asr_segments:
        v.asr_status = "pending"
        db.commit()
        from src.services.asr_queue import enqueue_asr
        enqueue_asr(v.id)

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
    meta = get_video_info(filepath)
    duration = meta["duration"]

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
                content = transcribe_by_api(audio_path, language=language)
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

    # 若 content > 200 字，加入 ASR 后台队列
    if content and len(content) > 200 and v2:
        v2.asr_status = "pending"
        db.commit()
        from src.services.asr_queue import enqueue_asr
        enqueue_asr(v2.id)

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
    meta = get_video_info(str(filepath))
    duration = meta["duration"]

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
            audio_path = extract_audio(str(filepath))
            content = transcribe_by_api(audio_path)
        except Exception as e:
            logger.error(f"ASR 提取语音失败:{e}")
    # 小红书等平台自带笔记文案
    if not content and video_info.description:
        content = video_info.description
        logger.info("使用平台描述作为文案: %d 字", len(content))

    v.status = "completed"
    v.content = content
    db.add(v)
    db.commit()
    db.refresh(v)

    # 若 content > 200 字，加入 ASR 后台队列
    if content and len(content) > 200:
        v.asr_status = "pending"
        db.commit()
        from src.services.asr_queue import enqueue_asr
        enqueue_asr(v.id)

    return _video_to_dict(v)


def _sse_event(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data}, ensure_ascii=False)}\n\n"


async def download_video_stream(db: Session, data: VideoDownloadRequest):
    """SSE 生成器：带进度的视频下载流程。"""
    from src.db.engine import get_session

    db = get_session()
    try:
        query_text = data.urls.strip()
        if not query_text:
            yield _sse_event("error", {"message": "请提供视频地址或分享内容"})
            return

        url_match = re.search(r'https?://[^\s,，。；！？、“”‘’【】《》<>^`{|}]+', query_text)
        if url_match:
            query_text = url_match.group(0)

        dest = ensure_date_dir(get_config("source_dir"), "tmp.mp4")
        dest.parent.mkdir(parents=True, exist_ok=True)

        # 阶段1: 视频下载
        yield _sse_event("progress", {"stage": "download", "progress": 0, "message": "开始下载..."})

        progress_queue = asyncio.Queue()

        def on_download_progress(percent):
            progress_queue.put_nowait(percent)

        download_task = asyncio.create_task(
            download.process_download(query_text, dest.parent, data.proxy or None, progress_callback=on_download_progress)
        )

        last_pct = 0
        while not download_task.done():
            try:
                pct = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                if pct > last_pct:
                    last_pct = pct
                    yield _sse_event("progress", {"stage": "download", "progress": pct, "message": f"下载中 {pct}%"})
            except asyncio.TimeoutError:
                continue

        video_info, filepath = download_task.result()
        yield _sse_event("progress", {"stage": "download", "progress": 100, "message": "下载完成"})

        # 获取视频元数据
        meta = get_video_info(str(filepath))
        duration = meta["duration"]

        # 创建数据库记录
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
            # 阶段2: 提取音频
            yield _sse_event("progress", {"stage": "audio", "progress": 0, "message": "正在提取音频..."})
            try:
                audio_path = extract_audio(str(filepath))
                yield _sse_event("progress", {"stage": "audio", "progress": 100, "message": "音频提取完成"})
            except Exception as e:
                yield _sse_event("progress", {"stage": "audio", "progress": 100, "message": f"音频提取失败: {e}"})
                audio_path = None

            # 阶段3: ASR 转文本
            if audio_path:
                yield _sse_event("progress", {"stage": "asr", "progress": 0, "message": "正在识别文本..."})
                try:
                    content = transcribe_by_api(audio_path)
                    yield _sse_event("progress", {"stage": "asr", "progress": 100, "message": "文案提取完成"})
                except Exception as e:
                    yield _sse_event("progress", {"stage": "asr", "progress": 100, "message": f"文案提取失败: {e}"})
        else:
            if video_info.description:
                content = video_info.description

        v.content = content
        db.add(v)
        db.commit()
        db.refresh(v)

        # 若 content > 200 字，加入 ASR 后台队列
        if content and len(content) > 200:
            v.asr_status = "pending"
            db.commit()
            from src.services.asr_queue import enqueue_asr
            enqueue_asr(v.id)

        yield _sse_event("complete", {"data": _video_to_dict(v)})
    except Exception as e:
        logger.error("下载流处理失败: %s", e)
        yield _sse_event("error", {"message": str(e)})
    finally:
        db.close()


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


def extract_audio_to_material(db: Session, video_id: int):
    """从原始视频提取音频轨道，创建为音频素材。"""
    from src.config import API_BASE_URL, get_config as _get_config
    from src.db.models import Material
    from src.processing.ffmpeg import FFMPEG
    from src.utils import ensure_date_dir, _CREATIONFLAGS

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    src_path = Path(v.filepath)
    out_name = f"{src_path.stem}_audio.mp3"
    out_path = ensure_date_dir(_get_config("material_dir"), out_name)

    cmd = [
        FFMPEG, "-i", str(src_path),
        "-vn", "-c:a", "libmp3lame", "-q:a", "2",
        "-y", str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, creationflags=_CREATIONFLAGS)

    material = Material(
        type="audio",
        content=v.content or "",
        start_time=0.0,
        end_time=v.duration or 0.0,
        filename=out_name,
        filepath=str(out_path),
        thumbnail="",
        status=1,
        folder_id=v.folder_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    return {
        "id": material.id,
        "type": material.type,
        "filename": material.filename,
        "duration": material.end_time,
        "folder_id": material.folder_id,
        "file_url": f"{API_BASE_URL}/api/materials/{material.id}/file",
    }


def smart_split_analyze(db: Session, video_id: int, audio_path: str | None, language: str) -> dict:
    import json as json_mod
    from src.processing.asr import transcribe
    from src.processing.paragraph import _timegap_merge

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")

    # 有预存的 ASR 结果 → 直接用时间间隔合并，速度快
    if v.asr_segments:
        try:
            asr_segments_list = json_mod.loads(v.asr_segments)
            if asr_segments_list:
                logger.info("  → 使用预存 ASR 结果，跳过音频提取和 ASR（共 %d 个片段）", len(asr_segments_list))
                paragraphs = _timegap_merge(asr_segments_list)
                items = [
                    ParagraphItem(seq_index=p["seq_index"], start=p["start"], end=p["end"], text=p["text"])
                    for p in paragraphs
                ]
                return {
                    "data": SplitAnalyzeOut(paragraphs=items, total_duration=v.duration,
                                            asr_cached=True).model_dump(mode="json"),
                    "message": f"分析完成（复用预存 ASR），共 {len(items)} 个自然段落",
                }
        except (json_mod.JSONDecodeError, TypeError):
            logger.warning("ASR 预存数据解析失败，回退到实时处理")

    # ASR 队列处理中
    if v.asr_status in ("pending", "processing"):
        raise fail_response(status_code=202, message=f"ASR 正在后台处理中（状态: {v.asr_status}），请稍后再试")

    try:
        logger.info("  → 开始 ASR 语音识别...")
        asr_segments = transcribe(audio_path, language=language)
    except Exception as e:
        raise fail_response(status_code=500, message=f"语音识别失败: {e}")

    if not asr_segments:
        raise fail_response(status_code=400, message="ASR 转录未产生任何片段")

    logger.info("  → ASR 完成，共 %d 个片段", len(asr_segments))

    paragraphs = merge_into_paragraphs(asr_segments)

    items = [
        ParagraphItem(seq_index=p["seq_index"], start=p["start"], end=p["end"], text=p["text"])
        for p in paragraphs
    ]
    return {
        "data": SplitAnalyzeOut(paragraphs=items, total_duration=v.duration).model_dump(mode="json"),
        "message": f"分析完成，共 {len(items)} 个自然段落",
    }


def _do_split_cut(video_id: int, paragraph_dicts: list[dict], extract_text: bool, remove_audio: bool) -> dict:
    """在独立线程中执行切割，使用独立的 DB 会话。"""
    from src.db.engine import get_session as _get_session
    db2 = _get_session()
    try:
        items = [
            ParagraphItem(seq_index=p["seq_index"], start=p["start"], end=p["end"], text=p.get("text", ""))
            for p in paragraph_dicts
        ]
        result = split_cut(db2, video_id, items, extract_text, remove_audio)
        return result.model_dump(mode="json")
    finally:
        db2.close()


async def smart_split_stream(db: Session, video_id: int, language: str, extract_text: bool, remove_audio: bool):
    """SSE 生成器：一站式智能分割，实时推送进度。"""
    import asyncio
    import json as json_mod
    import time
    from src.processing.asr import transcribe
    from src.processing.paragraph import _timegap_merge, merge_into_paragraphs
    from src.db.engine import get_session

    db = get_session()
    t_total_start = time.time()
    logger.info("[智能分割] ===== 开始 video_id=%s =============================", video_id)

    try:
        v = db.query(Video).get(video_id)
        if not v:
            yield _sse_event("error", {"message": "视频不存在"})
            return
        if not Path(v.filepath).exists():
            yield _sse_event("error", {"message": "视频文件不存在"})
            return

        logger.info("[智能分割] 视频: %s, 时长: %.1fs, 文件: %s", v.filename, v.duration or 0, v.filepath)

        # ASR 后台处理中
        if v.asr_status in ("pending", "processing"):
            logger.info("[智能分割] ASR 状态=%s，拒绝处理", v.asr_status)
            yield _sse_event("error", {"message": f"ASR 正在后台处理中（状态: {v.asr_status}），请稍后再试"})
            return

        asr_segments = None
        had_cached_asr = False

        # 有预存 ASR → 跳过音频提取和 ASR
        if v.asr_segments:
            try:
                cached = json_mod.loads(v.asr_segments)
                if cached:
                    had_cached_asr = True
                    logger.info("[智能分割] 步骤1: 使用预存 ASR（%d 个片段），跳过音频提取和 ASR", len(cached))
                    yield _sse_event("progress", {"stage": "audio_extract", "progress": 100, "message": "跳过（使用预存 ASR）"})
                    yield _sse_event("progress", {"stage": "asr", "progress": 100, "message": f"使用预存 ASR 结果，共 {len(cached)} 个片段"})
                    asr_segments = cached
            except (json_mod.JSONDecodeError, TypeError):
                logger.warning("[智能分割] 预存 ASR 解析失败，回退到实时处理")

        if not asr_segments:
            # Step 1: 提取音频
            t0 = time.time()
            logger.info("[智能分割] 步骤1: 开始提取音频...")
            yield _sse_event("progress", {"stage": "audio_extract", "progress": 0, "message": "正在提取音频..."})
            audio_path = await asyncio.to_thread(extract_audio, v.filepath)
            t1 = time.time()
            logger.info("[智能分割] 步骤1: 音频提取完成，耗时 %.2fs, 路径=%s", t1 - t0, audio_path)
            yield _sse_event("progress", {"stage": "audio_extract", "progress": 100, "message": f"音频提取完成 ({t1 - t0:.1f}s)"})

            # Step 2: ASR 语音识别
            t0 = time.time()
            logger.info("[智能分割] 步骤2: 开始 ASR 语音识别...")
            yield _sse_event("progress", {"stage": "asr", "progress": 0, "message": "正在进行语音识别..."})
            asr_segments = await asyncio.to_thread(transcribe, audio_path, language)
            t1 = time.time()
            if not asr_segments:
                logger.error("[智能分割] 步骤2: ASR 未产生任何片段")
                yield _sse_event("error", {"message": "ASR 转录未产生任何片段"})
                return
            logger.info("[智能分割] 步骤2: ASR 完成，耗时 %.2fs, 产出 %d 个片段", t1 - t0, len(asr_segments))
            yield _sse_event("progress", {"stage": "asr", "progress": 100, "message": f"ASR 完成 ({t1 - t0:.1f}s)，共 {len(asr_segments)} 个片段"})

            # 持久化 ASR 结果，后续重新分割时无需再次提取
            v.asr_segments = json_mod.dumps(asr_segments, ensure_ascii=False)
            v.asr_status = "completed"
            db.commit()
            logger.info("[智能分割] ASR 结果已持久化到数据库，共 %d 个片段", len(asr_segments))

        # Step 3: 段落合并
        t0 = time.time()
        logger.info("[智能分割] 步骤3: 开始段落合并（%d 个片段，use_llm=%s）...", len(asr_segments), not had_cached_asr)
        yield _sse_event("progress", {"stage": "paragraph_merge", "progress": 0, "message": "正在分析语义段落..."})
        if had_cached_asr:
            paragraphs = _timegap_merge(asr_segments)
        else:
            paragraphs = await asyncio.to_thread(merge_into_paragraphs, asr_segments)
        t1 = time.time()

        if not paragraphs:
            logger.error("[智能分割] 步骤3: 段落合并未产生任何段落")
            yield _sse_event("error", {"message": "未能识别出任何有效段落"})
            return
        logger.info("[智能分割] 步骤3: 段落合并完成，耗时 %.2fs, %d 个片段 → %d 个段落", t1 - t0, len(asr_segments), len(paragraphs))
        yield _sse_event("progress", {"stage": "paragraph_merge", "progress": 100, "message": f"分析完成 ({t1 - t0:.1f}s)，共 {len(paragraphs)} 个自然段落"})

        # Step 4: 切割视频
        t0 = time.time()
        logger.info("[智能分割] 步骤4: 开始切割 %d 个段落...", len(paragraphs))
        yield _sse_event("progress", {"stage": "cut", "progress": 0, "message": f"正在切割 {len(paragraphs)} 个片段..."})
        cut_result = await asyncio.to_thread(_do_split_cut, video_id, paragraphs, extract_text, remove_audio)
        t1 = time.time()
        material_count = cut_result.get("material_count", 0)
        logger.info("[智能分割] 步骤4: 切割完成，耗时 %.2fs, 产出 %d 个素材", t1 - t0, material_count)
        yield _sse_event("progress", {"stage": "cut", "progress": 100, "message": f"切割完成 ({t1 - t0:.1f}s)"})

        t_total = time.time() - t_total_start
        logger.info("[智能分割] ===== 全部完成 video_id=%s, 总耗时 %.2fs =============================", video_id, t_total)
        yield _sse_event("complete", {"data": cut_result})

    except Exception as e:
        t_total = time.time() - t_total_start
        logger.error("[智能分割] 失败 video_id=%s, 总耗时 %.2fs: %s", video_id, t_total, e)
        yield _sse_event("error", {"message": str(e)})
    finally:
        db.close()


def split_cut(db: Session, video_id: int, paragraphs: list, extract_text: bool, remove_audio: bool) -> dict:
    import os
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.processing.ffmpeg import split_video_clip, split_clip_and_extract_audio
    from src.db.models import Material as MaterialModel
    from src.api.schemas import MaterialOut

    t_cut_start = time.time()
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    if not paragraphs:
        return SplitCutOut(material_count=0, material_ids=[], materials=[])

    logger.info("[split_cut] 开始: %d 个段落, extract_text=%s, remove_audio=%s",
                 len(paragraphs), extract_text, remove_audio)

    def _process_paragraph(p):
        seg_path = ensure_date_dir(get_config("material_dir"), f"seg_{video_id}_{p.seq_index}.mp4")
        seg_path.parent.mkdir(parents=True, exist_ok=True)
        text = p.text or ""
        need_asr = extract_text and not text.strip()

        if need_asr:
            seg_audio = str(ensure_date_dir(
                get_config("material_dir"), f"seg_audio_{video_id}_{p.seq_index}.wav"))
            try:
                split_clip_and_extract_audio(
                    video_path=v.filepath,
                    start=p.start,
                    end=p.end,
                    video_output=str(seg_path),
                    audio_output=seg_audio,
                    no_audio=remove_audio,
                )
            except Exception:
                return None
            try:
                text = transcribe_by_api(seg_audio)
            except Exception:
                text = ""
            finally:
                Path(seg_audio).unlink(missing_ok=True)
        else:
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
                return None

        thumbnail = generate_thumbnail(str(seg_path))
        return {
            "seg_path": seg_path,
            "text": text,
            "title": p.title,
            "start": p.start,
            "end": p.end,
            "thumbnail": thumbnail,
        }

    max_workers = min(len(paragraphs), 6)
    results = [None] * len(paragraphs)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_process_paragraph, p): i
            for i, p in enumerate(paragraphs)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                results[idx] = None

    materials = []
    material_ids = []
    for r in results:
        if r is None:
            continue
        mat_filename = r["title"] or r["seg_path"].name
        mat = MaterialModel(
            type="video",
            content=r["text"],
            start_time=r["start"],
            end_time=r["end"],
            frame_width=v.frame_width,
            frame_height=v.frame_height,
            frame_rate=v.frame_rate,
            filename=mat_filename,
            filepath=str(r["seg_path"]),
            thumbnail=r["thumbnail"],
        )
        db.add(mat)
        db.flush()
        material_ids.append(mat.id)
        materials.append(MaterialOut.model_validate(mat).model_dump(mode="json"))

        if r["text"]:
            try:
                from src.db.vector import VectorStore
                VectorStore().add_material(mat.id, r["text"], {
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
    t_cut_total = time.time() - t_cut_start
    failed_count = sum(1 for r in results if r is None)
    logger.info("[split_cut] 完成: %d/%d 成功, %d 失败, 总耗时 %.2fs, 向量化 %d 个素材",
                 len(material_ids), len(paragraphs), failed_count, t_cut_total, len([r for r in results if r and r.get("text")]))
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
    import threading
    from src.db.engine import SessionLocal
    from src.db.models import Note as NoteModel
    from src.api.schemas import NoteOut

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not v.content:
        raise fail_response(status_code=400, message="视频暂无文案")

    folder = db.query(NoteModel).filter(
        NoteModel.is_system == True,
        NoteModel.tp == "folder",
    ).first()

    note = NoteModel(
        title=v.filename or f"视频 #{video_id} 笔记",
        content=v.content,
        parent_id=folder.id if folder else None,
        tp="note",
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    note_id = note.id
    raw_content = v.content

    def _format_in_background():
        from src.services.agents import call_agent
        from src.logger import default_logger as logger
        try:
            formatted = call_agent("note_ast", raw_content, max_tokens=4000)
            if formatted and formatted != raw_content:
                bg_db = SessionLocal()
                try:
                    n = bg_db.query(NoteModel).get(note_id)
                    if n:
                        n.content = formatted
                        bg_db.commit()
                finally:
                    bg_db.close()
        except Exception as e:
            logger.warning("笔记格式化失败: %s", e)

    threading.Thread(target=_format_in_background, daemon=True).start()

    return NoteOut.model_validate(note).model_dump(mode="json")
