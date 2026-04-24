"""编排视频处理和字幕生成流水线。"""

from datetime import datetime
from pathlib import Path

from src.config import OUTPUT_DIR, SUBTITLE_CROP_BOTTOM
from src.core.database import get_session, init_db
from src.core.vector_store import VectorStore
from src.models.models import GeneratedVideo, GeneratedVideoMaterial, Material, Video
from src.processing.paragraph import merge_into_paragraphs
from src.processing.video import (
    extract_audio,
    get_video_duration,
    get_video_metadata,
    separate_vocals,
    split_video_clip,
)
from src.query.llm_optimizer import expand_text, search_queries
from src.query.search import search_materials
from src.query.video_synth import concat_videos
from src.video.extract import get_timestamps


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

    print(f"[1/6] 正在提取时间轴（字幕/ASR）从 {video_path.name}...")
    segments = get_timestamps(str(video_path), language=language)
    if not segments:
        raise RuntimeError("未提取到字幕或 ASR 内容。")
    print(f"  → 检测到 {len(segments)} 个片段")

    print(f"[2/6] 正在合并片段为段落...")
    paragraphs = merge_into_paragraphs(segments)
    print(f"  → 形成 {len(paragraphs)} 个段落")

    print(f"[3/6] 正在获取视频元数据...")
    duration = get_video_duration(str(video_path))
    meta = get_video_metadata(str(video_path))
    print(f"  → {duration:.1f} 秒, {meta['frame_width']}x{meta['frame_height']} @ {meta['frame_rate']}fps")

    print(f"[4/6] 正在提取音频并分离人声...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = extract_audio(str(video_path))
    vocals_path = separate_vocals(audio_path)
    print(f"  → 人声已分离: {Path(vocals_path).name}")

    print(f"[5/6] 正在分割视频片段并分批存储...")
    session = get_session()
    video_stem = video_path.stem
    store = VectorStore()
    total_materials = 0
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

            for i, p in enumerate(batch):
                idx = batch_start + i
                clip_filename = f"{video_stem}_clip_{idx:04d}.mp4"
                clip_path = str(OUTPUT_DIR / clip_filename)

                # 去除人声和音乐，如有配置则裁掉底部字幕区域
                crop = None
                if SUBTITLE_CROP_BOTTOM > 0:
                    crop_h = meta["frame_height"] - SUBTITLE_CROP_BOTTOM
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

            # 提交本批数据库事务
            session.commit()
            print(f"    第 {batch_start // batch_size + 1} 批: 已保存 {len(batch_ids)} 个素材")

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
                    "filepath": str(OUTPUT_DIR / f"{video_stem}_clip_{batch_start + i:04d}.mp4"),
                })
                for i, mid in enumerate(batch_ids)
            ]
            store.add_materials_batch(items)
            print(f"    第 {batch_start // batch_size + 1} 批: 已向量化 {len(items)} 个素材")
            total_materials += len(batch_ids)

        print(f"  → 共生成 {total_materials} 个素材片段")
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

    print("✓ 处理完成。")
    return {"material_count": len(paragraphs)}


def search_and_generate(
    query: str,
    output_path: str | None = None,
    frame_width: int | None = None,
    frame_height: int | None = None,
    frame_rate: float | None = None,
) -> dict:
    """运行混剪流水线：扩写 → 逐句检索 → 去重排序 → 拼接 → 配音。

    处理流程：
      1. 用 LLM 将简短输入扩写为丰富的叙事脚本
      2. 将脚本拆分为句子，每句分别搜索向量库（top_1），保证每句匹配最相关画面
      3. 去重：同一个素材被多句命中时只保留第一次出现的位置
      4. 按时序排序，保证画面内容连贯
      5. 直接拼接素材片段（无转场）
      6. 将扩写文本合成为语音，为混剪视频配音

    参数：
        query: 用户输入的简短文本描述。
        output_path: 输出视频文件路径（为 None 时自动生成）。

    返回包含生成文件路径的摘要字典。
    """
    init_db()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] 正在扩写输入文本...")
    script = expand_text(query)
    print(f"  → {script[:120]}...")

    print(f"[2/5] 正在拆分检索单元...")
    queries = search_queries(script)
    print(f"  → 拆分为 {len(queries)} 个检索单元")

    print(f"[3/5] 逐句检索 → 去重 → 排序...")
    seen_ids = set()
    matched_materials = []

    for i, q in enumerate(queries):
        print(f"    查询 {i+1}/{len(queries)}: \"{q[:50]}...\"", end="")
        results = search_materials(
            q, top_k=1,
            frame_width=frame_width,
            frame_height=frame_height,
            frame_rate=frame_rate,
        )
        if not results:
            print(" × 无匹配")
            continue
        best = results[0]
        mid = best["material_id"]
        if mid in seen_ids:
            print(f" → #{mid} 已存在，跳过")
            continue
        seen_ids.add(mid)
        matched_materials.append(best)
        print(f" → #{mid} [{best['start_time']:.1f}s-{best['end_time']:.1f}s]")

    if not matched_materials:
        print("  → 未找到匹配素材。")
        return {"error": "未找到匹配素材。"}

    # 按时序排序，保证画面连贯
    matched_materials.sort(key=lambda r: (r["start_time"], r["material_id"]))

    print(f"  → 最终 {len(matched_materials)} 个素材：")
    for r in matched_materials:
        print(f"     #{r['material_id']} [{r['start_time']:.1f}s-{r['end_time']:.1f}s] {r['content'][:60]}...")

    clip_paths = []
    seen_paths = set()
    for r in matched_materials:
        fp = r.get("filepath", "")
        if fp and Path(fp).exists() and fp not in seen_paths:
            seen_paths.add(fp)
            clip_paths.append(fp)
    if not clip_paths:
        print("  × 素材文件不存在。")
        return {"error": "素材文件不存在。"}

    print(f"[4/5] 正在拼接混剪（{len(clip_paths)} 个片段）...")
    concat_output = output_path or str(Path(OUTPUT_DIR).parent / "mixed" / "remix_concat.mp4")
    concat_videos(clip_paths, concat_output)
    print(f"  → {concat_output}")

    print(f"[5/5] 正在生成配音...")
    from src.tts.cosyvoice import dub_from_text

    try:
        final_output = output_path or str(Path(OUTPUT_DIR).parent / "mixed" / "remix_dubbed.mp4")
        dub_from_text(concat_output, script, output_path=str(Path(final_output).parent))
        print(f"  → {final_output}")
    except RuntimeError as e:
        print(f"  → 配音跳过: {e}")
        final_output = concat_output

    # 持久化混剪记录
    session = get_session()
    try:
        gen_video = GeneratedVideo(
            title=query,
            script=script,
            tts_voice="",
            output_filepath=final_output,
            status="completed",
            material_count=len(matched_materials),
            completed_at=datetime.utcnow(),
        )
        session.add(gen_video)
        session.flush()

        for idx, r in enumerate(matched_materials):
            association = GeneratedVideoMaterial(
                generated_video_id=gen_video.id,
                material_id=r["material_id"],
                sequence_order=idx,
                segment_start_time=r["start_time"],
                segment_end_time=r["end_time"],
            )
            session.add(association)

        session.commit()
        print(f"  → 已保存混剪记录 #{gen_video.id}")
    except Exception:
        session.rollback()
        print("  → 混剪记录保存失败（不影响输出文件）")
    finally:
        session.close()

    print("✓ 混剪完成。")
    return {
        "script": script,
        "queries": queries,
        "material_count": len(matched_materials),
        "clip_paths": clip_paths,
        "output_video": final_output,
    }
