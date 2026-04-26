"""混剪生成流水线：扩写 → 检索 → 拼接 → 配音。"""
import hashlib
from datetime import datetime
from pathlib import Path

from src.config import get_config
from src.utils import ensure_date_dir
from src.logger import default_logger as logger

from src.db.engine import get_session, init_db
from src.db.models import GeneratedVideo
from src.processing.ffmpeg import concat_videos
from src.services.search import search_materials
from src.services.llm import expand_text, search_queries


def expand_and_search(
    query: str,
    skip_expand: bool = False,
    script: str | None = None,
    frame_width: int | None = None,
    frame_height: int | None = None,
    frame_rate: float | None = None,
) -> dict:
    """阶段1：扩写(可选) → 拆分 → 检索素材。返回脚本和匹配的素材列表。"""
    if not skip_expand and len(query) < 300:
        logger.info("[1/5] 正在扩写输入文本...")
        script = expand_text(query)
        logger.info("  → %s...", script[:120])
    else:
        logger.info("[1/5] 跳过扩写，使用已有脚本")
        script = script or query

    logger.info("[2/5] 正在拆分检索单元...")
    queries = search_queries(script)
    logger.info("  → 拆分为 %d 个检索单元", len(queries))

    logger.info("[3/5] 逐句检索 → 去重 → 排序...")
    seen_ids = set()
    matched_materials = []

    for i, q in enumerate(queries):
        logger.info("    查询 %d/%d: \"%s...\"", i + 1, len(queries), q[:50])
        combined = f"{query} {q}" if query != q else q
        results = search_materials(
            combined, top_k=3,
            frame_width=frame_width,
            frame_height=frame_height,
            frame_rate=frame_rate,
        )
        if not results:
            logger.info(" × 无匹配")
            continue
        # 取第一个未使用过的结果，避免同一素材被多句重复选中
        chosen = None
        for best in results:
            if best["material_id"] not in seen_ids:
                chosen = best
                break
        if chosen is None:
            logger.info(" → 结果均已使用，跳过")
            continue
        seen_ids.add(chosen["material_id"])
        matched_materials.append(chosen)
        logger.info(" → #%d [%.1fs-%.1fs]", chosen["material_id"], chosen["start_time"], chosen["end_time"])

    if not matched_materials:
        logger.info("  → 未找到匹配素材。")
        return {"script": script, "queries": queries, "materials": [], "clip_paths": []}

    # 按时序排序，保证画面连贯
    matched_materials.sort(key=lambda r: (r["start_time"], r["material_id"]))

    logger.info("  → 最终 %d 个素材：", len(matched_materials))
    for r in matched_materials:
        logger.info("     #%d [%.1fs-%.1fs] %s...", r["material_id"], r["start_time"], r["end_time"], r["content"][:60])

    clip_paths = []
    seen_paths = set()
    for r in matched_materials:
        fp = r.get("filepath", "")
        if fp and Path(fp).exists() and fp not in seen_paths:
            seen_paths.add(fp)
            clip_paths.append(fp)

    return {
        "script": script,
        "queries": queries,
        "materials": matched_materials,
        "clip_paths": clip_paths,
    }


def search_and_generate(
    query: str,
    output_path: str | None = None,
    frame_width: int | None = None,
    frame_height: int | None = None,
    frame_rate: float | None = None,
    skip_expand: bool = False,
    script: str | None = None,
    voice: str | None = None,
    pre_selected_materials: list[dict] | None = None,
) -> dict:
    """运行混剪流水线：扩写 → 逐句检索 → 去重排序 → 拼接 → 配音。

    处理流程：
      1. 用 LLM 将简短输入扩写为丰富的叙事脚本（skip_expand=True 时跳过）
      2. 将脚本拆分为句子，每句分别搜索向量库（top_1），保证每句匹配最相关画面
      3. 去重：同一个素材被多句命中时只保留第一次出现的位置
      4. 按时序排序，保证画面内容连贯
      5. 直接拼接素材片段（无转场）
      6. 将扩写文本合成为语音，为混剪视频配音

    参数：
        query: 用户输入的简短文本描述。
        output_path: 输出视频文件路径（为 None 时自动生成）。
        skip_expand: 是否跳过 LLM 扩写步骤。
        script: 当 skip_expand=True 时使用的脚本内容。
        voice: 配音音色，为 None 时使用默认音色。

    返回包含生成文件路径的摘要字典。
    """
    init_db()

    # 阶段1：扩写 + 检索
    search_result = None
    if pre_selected_materials:
        matched_materials = pre_selected_materials
        if not skip_expand:
            from src.services.llm import expand_text
            script = expand_text(query)
        else:
            script = script or query
        clip_paths = []
        seen_paths = set()
        for r in matched_materials:
            fp = r.get("filepath", "")
            if fp and Path(fp).exists() and fp not in seen_paths:
                seen_paths.add(fp)
                clip_paths.append(fp)
    else:
        search_result = expand_and_search(
            query=query,
            skip_expand=skip_expand,
            script=script,
            frame_width=frame_width,
            frame_height=frame_height,
            frame_rate=frame_rate,
        )
        matched_materials = search_result["materials"]
        script = search_result["script"]
        clip_paths = search_result["clip_paths"]

    if not matched_materials:
        return {"error": "未找到匹配素材。"}

    # 阶段2：拼接 + 配音
    logger.info("[4/5] 正在拼接混剪（%d 个片段）...", len(clip_paths))
    prefix_file = hashlib.md5(script.encode()).hexdigest()
    concat_output = output_path or str(ensure_date_dir(get_config("mixed_dir"), f"{prefix_file}_concat.mp4"))
    concat_videos(clip_paths, concat_output, frame_width, frame_height)
    logger.info("  → %s", concat_output)

    # 计算视频总时长，限制脚本长度（4 字/秒）
    from src.processing.ffmpeg import get_video_duration
    total_dur = get_video_duration(concat_output) or 30.0
    max_chars = int(total_dur * 4)
    if len(script) > max_chars:
        logger.info("  脚本 %d 字超过 %d 字限制（%.1fs × 4），截取前 %d 字", len(script), max_chars, total_dur, max_chars)
        script = script[:max_chars]

    logger.info("[5/5] 正在生成配音...")
    from src.services.tts import synthesize, dub_video
    audio_filepath = None

    try:
        audio_filepath = synthesize(script, voice=voice)
        logger.info("  → 配音音频: %s", audio_filepath)
        final_output = output_path or str(ensure_date_dir(get_config("mixed_dir"), f"{prefix_file}_dubbed.mp4"))
        dub_video(concat_output, audio_filepath, output_path=final_output)
        logger.info("  → %s", final_output)

        # TTS 音频存入素材库（status=0 表示缓存素材），记录素材 ID
        tts_material_id = None
        try:
            from src.db.models import Material
            from datetime import datetime
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
            tts_session = get_session()
            try:
                tts_session.add(tts_material)
                tts_session.commit()
                tts_material_id = tts_material.id
                logger.info("  → TTS 音频已存入素材库 #%d（status=0）", tts_material_id)
            finally:
                tts_session.close()
        except Exception as e:
            logger.warning("  → TTS 素材入库失败（不影响输出）: %s", e)
    except RuntimeError as e:
        logger.warning("  → 配音跳过: %s", e)
        final_output = concat_output

    # 持久化混剪记录
    import json, uuid
    session = get_session()
    try:
        material_list = []
        current_frame = 0
        frame_rate_val = frame_rate or 30
        for idx, r in enumerate(matched_materials):
            clip_duration_frames = round(((r["end_time"] - r["start_time"]) or 10.0) * frame_rate_val)
            clip_duration_frames = max(clip_duration_frames, 30)
            clip_id = f"c-{uuid.uuid4().hex[:7]}"
            material_list.append({
                "id": clip_id,
                "type": r.get("type", "video"),
                "material_id": r["material_id"],
                "content": r.get("content", ""),
                "filepath": r.get("filepath", ""),
                "start": current_frame,
                "end": current_frame + clip_duration_frames,
                "frameCount": clip_duration_frames,
                "offsetL": 0,
                "offsetR": 0,
                "centerX": 50,
                "centerY": 50,
                "scale": 100,
                "width": r.get("frame_width", 1920) or 1920,
                "height": r.get("frame_height", 1080) or 1080,
                "fontSize": 48,
                "fontFamily": "sans-serif",
                "fontColor": "#ffffff",
                "bold": False,
                "italic": False,
                "shadow": False,
                "outline": False,
                "outlineColor": "#000000",
                "bgColor": "#000000",
                "bgEnabled": False,
                "textAlign": "center",
                "effect": "",
                "transitionIn": None,
            })
            current_frame += clip_duration_frames + 1

        tracks = [{"type": "video", "name": "主轨道", "list": material_list, "visible": True, "locked": False, "muted": True}]
        if audio_filepath and Path(audio_filepath).exists():
            from src.processing.ffmpeg import get_video_duration
            audio_dur_frames = round(get_video_duration(audio_filepath) * frame_rate_val)
            audio_clip = {
                "id": f"c-{uuid.uuid4().hex[:7]}",
                "type": "audio",
                "material_id": tts_material_id,
                "content": "配音",
                "filepath": audio_filepath,
                "start": 0,
                "end": audio_dur_frames,
                "frameCount": audio_dur_frames,
                "offsetL": 0,
                "offsetR": 0,
                "centerX": 50,
                "centerY": 50,
                "scale": 100,
            }
            tracks.append({"type": "audio", "name": "配音", "list": [audio_clip], "visible": False, "locked": False, "muted": False})

        gen_video = GeneratedVideo(
            title=query,
            script=script,
            tts_voice="",
            output_filepath=final_output,
            status="completed",
            frame_width=frame_width or 0,
            frame_height=frame_height or 0,
            frame_rate=frame_rate or 0,
            material_count=len(matched_materials),
            data=json.dumps({"tracks": tracks}, ensure_ascii=False),
            completed_at=datetime.utcnow(),
        )
        session.add(gen_video)
        session.commit()
        logger.info("  → 已保存混剪记录 #%d", gen_video.id)
    except Exception:
        session.rollback()
        logger.warning("  → 混剪记录保存失败（不影响输出文件）")
    finally:
        session.close()

    logger.info("✓ 混剪完成。")
    return {
        "script": script,
        "queries": search_result.get("queries", []) if search_result else [],
        "material_count": len(matched_materials),
        "clip_paths": clip_paths,
        "output_video": final_output,
    }
