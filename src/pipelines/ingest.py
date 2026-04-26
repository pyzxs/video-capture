"""视频摄入流水线：提取时间轴 → 生成段落 → 存储素材 → 向量化。"""

from datetime import datetime
from pathlib import Path

from src.config import get_config
from src.utils import ensure_date_dir
from src.logger import default_logger as logger

from src.db.engine import get_session, init_db
from src.db.vector import VectorStore
from src.db.models import GeneratedVideo, Material, Video
from src.processing.paragraph import merge_into_paragraphs
from src.processing.ffmpeg import (
    extract_audio,
    get_video_duration,
    get_video_metadata,
    separate_vocals,
    split_video_clip,
)
from src.processing.subtitle import get_timestamps


def process_video(video_path: str, language: str = "zh") -> dict:
    """运行完整输入流水线：时间轴 → 素材分割 → 存储 → 向量化。

    时间轴提取优先尝试嵌入式软字幕；如果没有找到则回退到
    ffmpeg 音频提取 + Whisper ASR。

    处理流程：
      1. 提取字幕/ASR 时间轴
      2. 合并为语义段落
      3. 提取视频原始音频并分离人声（去除背景音乐）
      4. 按段落时间范围分割视频片段（使用分离后人声）
      5. 将每个片段作为素材写入数据库并向量化

    返回素材数量摘要字典。
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    init_db()

    logger.info("[1/6] 正在提取时间轴（字幕/ASR）从 %s...", video_path.name)
    segments = get_timestamps(str(video_path), language=language)
    if not segments:
        raise RuntimeError("未提取到字幕或 ASR 内容。")
    logger.info("  → 检测到 %d 个片段", len(segments))

    logger.info("[2/6] 正在合并片段为段落...")
    paragraphs = merge_into_paragraphs(segments)
    logger.info("  → 形成 %d 个段落", len(paragraphs))

    logger.info("[3/6] 正在获取视频元数据...")
    duration = get_video_duration(str(video_path))
    meta = get_video_metadata(str(video_path))
    logger.info("  → %.1f 秒, %dx%d @ %.2ffps", duration, meta["frame_width"], meta["frame_height"], meta["frame_rate"])

    logger.info("[4/6] 正在提取音频并分离人声...")
    audio_path = extract_audio(str(video_path))
    vocals_path = separate_vocals(audio_path)
    logger.info("  → 人声已分离: %s", Path(vocals_path).name)

    logger.info("[5/6] 正在分割视频片段并分批存储...")
    session = get_session()
    video_stem = video_path.stem
    store = VectorStore()
    total_materials = 0
    all_material_ids = []
    batch_size = 20

    try:
        # 记录源视频信息
        full_text = " ".join(p["text"] for p in paragraphs)
        source_video = Video(
            filename=video_path.name,
            filepath=str(video_path.resolve()),
            duration=duration,
            frame_width=meta["frame_width"],
            frame_height=meta["frame_height"],
            frame_rate=meta["frame_rate"],
            content=full_text,
        )
        session.add(source_video)
        session.flush()

        for batch_start in range(0, len(paragraphs), batch_size):
            batch = paragraphs[batch_start : batch_start + batch_size]
            batch_ids = []

            batch_clip_paths = []
            for i, p in enumerate(batch):
                idx = batch_start + i
                clip_filename = f"{video_stem}_clip_{idx:04d}.mp4"
                clip_path = str(ensure_date_dir(get_config("material_dir"), clip_filename))
                batch_clip_paths.append(clip_path)

                # 去除人声和音乐，如有配置则裁掉底部字幕区域
                crop = None
                if get_config("subtitle_crop_bottom") > 0:
                    crop_h = meta["frame_height"] - get_config("subtitle_crop_bottom")
                    if crop_h % 2 != 0:
                        crop_h -= 1  # h264 要求偶数高度
                    crop = f"{meta['frame_width']}:{crop_h}:0:0"
                split_video_clip(
                    video_path=str(video_path),
                    vocals_path=vocals_path,
                    start=p["start"],
                    end=p["end"],
                    output_path=clip_path,
                    crop=crop,
                )

                material = Material(
                    type="video",
                    content=p["text"],
                    start_time=p["start"],
                    end_time=p["end"],
                    frame_width=meta["frame_width"],
                    frame_height=meta["frame_height"],
                    frame_rate=meta["frame_rate"],
                    filename=clip_filename,
                    filepath=clip_path,
                )
                session.add(material)
                session.flush()
                batch_ids.append(material.id)
                all_material_ids.append(material.id)

            # 提交本批数据库事务
            session.commit()
            logger.info("    第 %d 批: 已保存 %d 个素材", batch_start // batch_size + 1, len(batch_ids))

            # 向量化本批素材
            items = [
                (mid, batch[i]["text"], {
                    "type": "video",
                    "start_time": batch[i]["start"],
                    "end_time": batch[i]["end"],
                    "frame_width": meta["frame_width"],
                    "frame_height": meta["frame_height"],
                    "frame_rate": meta["frame_rate"],
                    "filename": f"{video_stem}_clip_{batch_start + i:04d}.mp4",
                    "filepath": batch_clip_paths[i],
                })
                for i, mid in enumerate(batch_ids)
            ]
            store.add_materials_batch(items)
            logger.info("    第 %d 批: 已向量化 %d 个素材", batch_start // batch_size + 1, len(items))
            total_materials += len(batch_ids)

        logger.info("  → 共生成 %d 个素材片段", total_materials)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # 清理临时音频文件
    try:
        Path(audio_path).unlink(missing_ok=True)
        Path(vocals_path).unlink(missing_ok=True)
    except OSError:
        pass

    logger.info("✓ 处理完成。")
    return {"material_count": len(paragraphs), "material_ids": all_material_ids}
