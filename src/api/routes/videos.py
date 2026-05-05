from fastapi import APIRouter, Depends, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.response import response_success
from src.api.schemas import (
    SmartAnalyzeRequest,
    SplitCutRequest,
    VideoDownloadRequest,
    VideoDubRequest,
    VideoUpdate,
)
from src.api.services.video_service import (
    delete_video,
    download_video_service,
    dub_video_service,
    get_video,
    get_video_file_path,
    get_video_status,
    list_videos,
    save_video_to_notes,
    smart_split_analyze,
    smart_split_extract_audio,
    smart_split_subtitles,
    split_analyze,
    split_cut,
    split_video_full,
    update_video,
    upload_video,
)

router = APIRouter(prefix="/videos", tags=["原始视频管理"])


@router.get("", description="获取原始视频列表")
def _list_videos(
    q: str | None = None,
    folder_id: int | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    return response_success(data=list_videos(db, q, folder_id, skip, limit))


@router.get("/{video_id}", description="获取视频详情")
def _get_video(video_id: int, db: Session = Depends(get_db)):
    return response_success(data=get_video(db, video_id))


@router.patch("/{video_id}", description="更新视频")
def _update_video(video_id: int, data: VideoUpdate, db: Session = Depends(get_db)):
    return response_success(data=update_video(db, video_id, data.filename, data.content), message="更新成功")


@router.post("/{video_id}/dub", description="为视频配音（TTS 合成 + 替换音轨）")
def _dub_video(video_id: int, data: VideoDubRequest, db: Session = Depends(get_db)):
    return response_success(data=dub_video_service(db, video_id, data.voice), message="配音完成")


@router.post("/upload", status_code=201)
def _upload_video(
    file: UploadFile,
    language: str = "zh",
    folder_id: int | None = Form(default=None),
    extract_text: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    data = upload_video(db, file, language, folder_id, extract_text)
    return response_success(data=data, message="上传成功", status_code=201)


@router.post("/download", description="网络下载视频")
async def _download_video(data: VideoDownloadRequest, db: Session = Depends(get_db)):
    result = await download_video_service(db, data)
    return response_success(data=result, message="视频下载成功")


@router.get("/{video_id}/file")
def _get_video_file(video_id: int, db: Session = Depends(get_db)):
    return FileResponse(get_video_file_path(db, video_id))


@router.get("/{video_id}/status")
def _get_video_status(video_id: int, db: Session = Depends(get_db)):
    return response_success(data=get_video_status(db, video_id).model_dump(mode="json"))


@router.delete("/{video_id}")
def _delete_video(video_id: int, db: Session = Depends(get_db)):
    return response_success(data=delete_video(db, video_id), message="删除成功")


@router.post("/{video_id}/split/analyze", description="分割视频 - 步骤1: 分析时间轴")
def _split_analyze(video_id: int, language: str = "zh", db: Session = Depends(get_db)):
    result = split_analyze(db, video_id, language)
    return response_success(data=result.model_dump(mode="json"), message="分析完成")


@router.post("/{video_id}/split/smart/subtitles", description="智能分割 - 步骤1: 分析视频软字幕")
def _smart_split_subtitles(video_id: int, db: Session = Depends(get_db)):
    result = smart_split_subtitles(db, video_id)
    return response_success(**result)


@router.post("/{video_id}/split/smart/extract-audio", description="智能分割 - 步骤2: 提取视频音频")
def _smart_split_extract_audio(video_id: int, db: Session = Depends(get_db)):
    result = smart_split_extract_audio(db, video_id)
    return response_success(**result)


@router.post("/{video_id}/split/smart/analyze", description="智能分割 - 步骤3+4: 语音识别与语义段落分析")
def _smart_split_analyze(video_id: int, data: SmartAnalyzeRequest, db: Session = Depends(get_db)):
    result = smart_split_analyze(db, video_id, data.audio_path, data.language, data.subtitles)
    return response_success(**result)


@router.post("/{video_id}/split/cut", description="分割视频 - 步骤2: 切割片段（仅保留画面，去除声音）")
def _split_cut(video_id: int, data: SplitCutRequest, db: Session = Depends(get_db)):
    result = split_cut(db, video_id, data.paragraphs, data.extract_text, data.remove_audio)
    return response_success(data=result.model_dump(mode="json"), message="分割完成")


@router.post("/{video_id}/save-to-notes", description="将视频文案保存到笔记（经笔记智能体排版）")
def _save_video_to_notes(video_id: int, db: Session = Depends(get_db)):
    return response_success(data=save_video_to_notes(db, video_id), message="已保存到笔记")


@router.post("/{video_id}/split")
def _split_video(video_id: int, language: str = "zh", db: Session = Depends(get_db)):
    result = split_video_full(db, video_id, language)
    return response_success(data=result.model_dump(mode="json"), message="分割完成")
