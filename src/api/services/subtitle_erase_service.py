"""视频字幕擦除服务：上传到 CMS → 提交擦除任务 → 查询结果 → 下载替换。"""
import time
from pathlib import Path

import requests

from src.api.response import fail_response
from src.config import get_config
from src.logger import get_logger
from src.processing.ffmpeg import get_video_info
from src.utils import generate_thumbnail

logger = get_logger("subtitle_erase")


def _cms_headers() -> dict:
    api_key = get_config("api_key")
    if not api_key:
        raise fail_response(status_code=502, message="未注册 CMS 用户")
    return {"X-Api-Key": api_key}


def submit_erase(filepath: str) -> dict:
    """将视频文件上传到 CMS 并提交字幕擦除任务。返回 task_id 等信息。"""
    if not filepath or not Path(filepath).exists():
        raise fail_response(status_code=404, message="视频文件不存在")

    headers = _cms_headers()
    cms_url = get_config("cms_base_url")

    logger.info("上传视频到 CMS 并提交擦除任务: %s", filepath)
    try:
        with open(filepath, "rb") as f:
            resp = requests.post(
                f"{cms_url}/api/proxy/subtitle-erase",
                files={"file": (Path(filepath).name, f)},
                headers=headers,
                timeout=600,
            )
        if resp.status_code >= 400:
            data = resp.json()
            raise fail_response(
                status_code=502,
                message=f"CMS 擦除任务提交失败: {data.get('message', resp.text[:200])}",
            )
        result = resp.json()
        return result.get("data", result)
    except requests.RequestException as e:
        raise fail_response(status_code=502, message=f"无法连接 CMS: {e}")


def query_erase(task_id: str, filepath: str = "") -> dict:
    """查询字幕擦除任务结果。若传入 filepath，任务完成时 CMS 会清理临时文件。"""
    headers = _cms_headers()
    cms_url = get_config("cms_base_url")

    params = {}
    if filepath:
        params["filepath"] = filepath

    try:
        resp = requests.get(
            f"{cms_url}/api/proxy/subtitle-erase/{task_id}",
            params=params,
            headers=headers,
            timeout=30,
        )
        if resp.status_code >= 400:
            data = resp.json()
            raise fail_response(
                status_code=502,
                message=f"CMS 查询任务失败: {data.get('message', resp.text[:200])}",
            )
        result = resp.json()
        return result.get("data", result)
    except requests.RequestException as e:
        raise fail_response(status_code=502, message=f"无法连接 CMS: {e}")


def apply_erase(filepath: str, task_id: str, db, orm_model, video_url: str = "") -> dict:
    """下载处理后的视频并替换原文件，更新数据库记录。
    若传入 video_url 则跳过查询 CMS 步骤。"""
    if video_url:
        processed_url = video_url
    else:
        # 1) 查询任务状态
        task_data = query_erase(task_id)
        if not task_data.get("success"):
            raise fail_response(
                status_code=400,
                message=f"任务未成功: {task_data.get('error', {}).get('message', '未知错误')}",
            )
        result = task_data.get("result", {})
        processed_url = result.get("video_url", "")

    if not processed_url:
        raise fail_response(
            status_code=400,
            message="任务尚未完成，暂无处理结果",
        )

    if not filepath or not Path(filepath).exists():
        raise fail_response(status_code=404, message="原视频文件不存在")

    # 2) 下载处理后的视频
    logger.info("下载擦除后的视频: %s", processed_url[:120])
    try:
        dl_resp = requests.get(processed_url, timeout=600, stream=True)
        if dl_resp.status_code >= 400:
            raise fail_response(
                status_code=502,
                message=f"下载处理视频失败 (HTTP {dl_resp.status_code})",
            )

        old_path = Path(filepath)
        new_name = f"{old_path.stem}_erased_{int(time.time())}{old_path.suffix}"
        new_filepath = old_path.parent / new_name

        with open(new_filepath, "wb") as f:
            for chunk in dl_resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = new_filepath.stat().st_size
        logger.info("下载完成: %s (%.2fMB)", new_filepath, file_size / 1024 / 1024)
    except requests.RequestException as e:
        raise fail_response(status_code=502, message=f"下载处理视频失败: {e}")

    # 3) 提取元数据并更新数据库
    meta = get_video_info(str(new_filepath))
    thumbnail = generate_thumbnail(str(new_filepath))

    record = db.query(type(orm_model)).get(orm_model.id)
    if not record:
        raise fail_response(status_code=404, message="数据库记录不存在")

    record.filepath = str(new_filepath)
    record.cms_filepath = str(old_path)  # 保存擦除前的原始文件路径
    record.frame_width = meta.get("width", record.frame_width)
    record.frame_height = meta.get("height", record.frame_height)
    record.frame_rate = meta.get("fps", record.frame_rate)
    # Video has duration field, Material uses start_time/end_time
    if hasattr(record, "duration"):
        record.duration = meta.get("duration", record.duration)
    if thumbnail:
        record.thumbnail = thumbnail
    db.commit()

    logger.info("文件已替换: id=%d 新路径=%s", record.id, new_filepath)

    return {
        "id": record.id,
        "filepath": str(new_filepath),
        "cms_filepath": str(old_path),
        "frame_width": record.frame_width,
        "frame_height": record.frame_height,
        "frame_rate": record.frame_rate,
    }
