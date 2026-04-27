import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.response import fail_response, response_success
from src.api.schemas import (
    ParagraphItem,
    SplitAnalyzeOut,
    SplitCutOut,
    SplitCutRequest,
    VideoDownloadRequest,
    VideoDubRequest,
    VideoOut,
    VideoSplitOut,
    VideoStatusOut,
    VideoUpdate,
)
from src.config import get_config
from src.db.models import Video
from src.logger import default_logger as logger
from src.pipelines import download
from src.processing.asr import transcribe_by_api
from src.processing.ffmpeg import get_video_duration, get_video_metadata, extract_audio
from src.processing.paragraph import merge_into_paragraphs
from src.processing.subtitle import get_timestamps
from src.utils import ensure_date_dir

router = APIRouter(prefix="/videos", tags=["原始视频管理"])


@router.get("", description="获取原始视频列表")
def list_videos(
        q: str | None = None,
        folder_id: int | None = None,
        skip: int = 0,
        limit: int = 20,
        db: Session = Depends(get_db),
):
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
    return response_success(data={
        "items": [VideoOut.model_validate(i).model_dump(mode="json") for i in items],
        "total": total,
    })


@router.get("/{video_id}", description="获取视频详情")
def get_video(video_id: int, db: Session = Depends(get_db)):
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    return response_success(data=v)


@router.patch("/{video_id}", description="更新视频")
def update_video(video_id: int, data: VideoUpdate, db: Session = Depends(get_db)):
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if data.filename is not None:
        v.filename = data.filename
    if data.content is not None:
        v.content = data.content
    db.commit()
    db.refresh(v)
    return response_success(data=VideoOut.model_validate(v).model_dump(mode="json"), message="更新成功")


@router.post("/{video_id}/dub", description="为视频配音（TTS 合成 + 替换音轨）")
def dub_video(video_id: int, data: VideoDubRequest, db: Session = Depends(get_db)):
    """使用视频文案合成语音并替换原视频音轨。"""
    from src.services.tts import dub_from_text
    from src.config import get_config

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
        result = dub_from_text(v.filepath, v.content, voice=data.voice, output_path=output_path)
        v.filepath = result
        db.commit()
        db.refresh(v)
        return response_success(
            data=VideoOut.model_validate(v).model_dump(mode="json"),
            message="配音完成",
        )
    except Exception as e:
        raise fail_response(status_code=500, message=f"配音失败: {e}")


@router.post("/upload", status_code=201)
def upload_video(
        file: UploadFile,
        language: str = "zh",
        folder_id: int | None = Form(default=None),
        extract_text: bool = Form(default=True),
        db: Session = Depends(get_db),
):
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
    content = ""
    if extract_text:
        try:
            try:
                audio_path = extract_audio(filepath)
                print(f"获取实际音频地址 {audio_path}")
                content = transcribe_by_api(audio_path, language=language)
            except Exception as e:
                logger.error(f"ASR 提取语音失败:{e}")
            new_status = "completed"
        except Exception as e:
            logger.error("ASR 处理失败: %s", e)
            new_status = "failed"
    else:
        new_status = "completed"

    v2 = db.query(Video).get(v.id)
    if v2:
        v2.status = new_status
        v2.content = content
        db.commit()
        db.refresh(v2)

    from src.api.schemas import VideoOut

    return response_success(data=VideoOut.model_validate(v2 or v).model_dump(mode="json"), message="上传成功",
                            status_code=201)


@router.post("/download", description="网络下载视频")
async def download_video(data: VideoDownloadRequest, db: Session = Depends(get_db)):
    """从网络下载视频（抖音/B站/快手/YouTube）。"""
    logger.info("请求信息: %s", data)
    query_text = data.urls.strip()
    if not query_text:
        raise fail_response(status_code=400, message="请提供视频地址或分享内容")

    # 从分享文案中提取第一个有效 URL（兼容抖音/快手等平台含中文的分享文本）
    import re
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
        folder_id=data.folder_id,
    )

    content = ""
    if data.extract_text:
        try:
            try:
                audio_path = extract_audio(str(filepath))
                print(f"获取实际音频地址 {audio_path}")
                content = transcribe_by_api(audio_path)
            except Exception as e:
                logger.error(f"ASR 提取语音失败:{e}")
            new_status = "completed"
        except Exception as e:
            logger.error("ASR 处理失败: %s", e)
            new_status = "failed"
    else:
        new_status = "completed"

    v.status = new_status
    v.content = content
    db.add(v)
    db.commit()
    db.refresh(v)

    from src.api.schemas import VideoOut

    return response_success(data=VideoOut.model_validate(v).model_dump(mode="json"), message="视频下载成功")


@router.get("/{video_id}/file")
def get_video_file(video_id: int, db: Session = Depends(get_db)):
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not v.filepath or not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="文件不存在")
    return FileResponse(v.filepath)


@router.get("/{video_id}/status")
def get_video_status(video_id: int, db: Session = Depends(get_db)):
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    return response_success(
        data=VideoStatusOut(id=v.id, status=v.status, content=v.content, filename=v.filename).model_dump(mode="json"))


@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if v.filepath and Path(v.filepath).exists():
        Path(v.filepath).unlink(missing_ok=True)
    db.delete(v)
    db.commit()
    return response_success(data={"ok": True}, message="删除成功")


@router.post("/{video_id}/split/analyze", description="分割视频 - 步骤1: 分析时间轴")
def split_analyze(video_id: int, language: str = "zh", db: Session = Depends(get_db)):
    """分析视频，提取时间轴并合并为语义段落。"""
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
    return response_success(data=SplitAnalyzeOut(
        paragraphs=items,
        total_duration=v.duration,
    ).model_dump(mode="json"), message="分析完成")


@router.post("/{video_id}/split/cut", description="分割视频 - 步骤2: 切割片段（仅保留画面，去除声音）")
def split_cut(video_id: int, data: SplitCutRequest, db: Session = Depends(get_db)):
    """根据段落数据切割视频片段，生成无音频的纯视频素材。"""
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    import subprocess
    from src.processing.ffmpeg import split_video_clip, extract_audio
    from src.db.models import Material as MaterialModel
    from src.processing.asr import transcribe_by_api
    from src.config import BASE_DIR

    ffmpeg_cmd = f"{BASE_DIR}/bin/ffmpeg"

    from src.api.schemas import MaterialOut

    materials = []
    material_ids = []
    for p in data.paragraphs:
        seg_path = ensure_date_dir(get_config("material_dir"),
                                   f"seg_{video_id}_{p.seq_index}.mp4")
        seg_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            split_video_clip(
                video_path=v.filepath,
                vocals_path="",
                start=p.start,
                end=p.end,
                output_path=str(seg_path),
                no_audio=data.remove_audio,
            )
        except Exception:
            continue

        # 提取该段文本（为空则通过 ASR 自动识别）
        text = p.text or ""
        if data.extract_text and not text.strip():
            try:
                seg_audio = str(ensure_date_dir(
                    get_config("material_dir"), f"seg_audio_{video_id}_{p.seq_index}.wav"))
                subprocess.run([
                    ffmpeg_cmd, "-ss", str(p.start), "-to", str(p.end),
                    "-i", str(v.filepath),
                    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                    "-y", seg_audio,
                ], check=True, capture_output=True)
                text = transcribe_by_api(seg_audio)
            except Exception:
                text = ""
            finally:
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
    return response_success(data=SplitCutOut(
        material_count=len(material_ids),
        material_ids=material_ids,
        materials=materials,
    ).model_dump(mode="json"), message="分割完成")


@router.post("/{video_id}/save-to-notes", description="将视频文案保存到笔记（经笔记智能体排版）")
def save_video_to_notes(video_id: int, db: Session = Depends(get_db)):
    """将视频文案通过笔记助手排版后保存到默认笔记文件夹。"""
    from src.db.models import Note as NoteModel
    from src.services.agents import call_agent

    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not v.content:
        raise fail_response(status_code=400, message="视频暂无文案")

    # 通过笔记助手排版
    formatted = call_agent("note_ast", v.content, max_tokens=4000)

    # 查找系统默认笔记文件夹
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

    from src.api.schemas import NoteOut
    return response_success(
        data=NoteOut.model_validate(note).model_dump(mode="json"),
        message="已保存到笔记",
    )


@router.post("/{video_id}/split")
def split_video(video_id: int, language: str = "zh", db: Session = Depends(get_db)):
    """兼容旧版：一次完成分析和切割（素材无音频）。"""
    v = db.query(Video).get(video_id)
    if not v:
        raise fail_response(status_code=404, message="视频不存在")
    if not Path(v.filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    timestamps = get_timestamps(v.filepath, language=language)
    if not timestamps:
        raise fail_response(status_code=400, message="未能提取到时间轴信息")

    paragraphs = merge_into_paragraphs(timestamps)

    from src.processing.ffmpeg import split_video_clip
    from src.db.models import Material as MaterialModel

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
    return response_success(data=VideoSplitOut(material_count=len(material_ids), material_ids=material_ids).model_dump(mode="json"),
                            message="分割完成")
