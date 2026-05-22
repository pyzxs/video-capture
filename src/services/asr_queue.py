"""ASR 后台队列：单 Worker 线程串行处理，不连续执行。"""
import json
import threading
from queue import Queue

from src.logger import default_logger as logger

_queue = Queue()
_worker_started = False


def start_asr_worker():
    """启动单线程 ASR Worker（幂等）。"""
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    threading.Thread(target=_worker_loop, daemon=True).start()
    logger.info("ASR 队列 Worker 已启动")


def enqueue_asr(video_id: int):
    """将 video 加入 ASR 处理队列。"""
    _queue.put(video_id)
    logger.info(f"ASR 任务入队: video_id={video_id}, 队列长度={_queue.qsize()}")


def _worker_loop():
    """Worker 主循环：阻塞等待，逐个处理。"""
    while True:
        video_id = _queue.get()
        try:
            _process_one(video_id)
        except Exception:
            logger.exception(f"ASR 处理失败: video_id={video_id}")
        finally:
            _queue.task_done()


def _process_one(video_id: int):
    """处理单个视频：提取音频 → ASR → 存储结果。"""
    from src.db.engine import get_session, SessionLocal
    from src.db.models import Video
    from src.processing.ffmpeg import extract_audio
    from src.processing.asr import transcribe

    db = get_session()
    try:
        video = db.query(Video).get(video_id)
        if not video:
            logger.warning(f"ASR: 视频不存在 video_id={video_id}")
            return
        if not video.filepath:
            logger.warning(f"ASR: 视频无文件路径 video_id={video_id}")
            return

        logger.info(f"ASR 开始处理: video_id={video_id}, file={video.filepath}")
        video.asr_status = "processing"
        db.commit()

        # 提取音频
        audio_path = extract_audio(video.filepath)

        # ASR 转录
        segments = transcribe(audio_path)

        # 存储结果
        video.asr_segments = json.dumps(segments, ensure_ascii=False)
        video.asr_status = "completed"
        db.commit()
        logger.info(f"ASR 处理完成: video_id={video_id}, segments={len(segments)}")

    except Exception:
        db.rollback()
        try:
            video = db.query(Video).get(video_id)
            if video:
                video.asr_status = "failed"
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()
