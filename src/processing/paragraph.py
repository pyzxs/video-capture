"""基于时间间隔或大模型分析的段落合并。"""

import re

from src.config import (
    PARAGRAPH_GAP_THRESHOLD,
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    ANTHROPIC_BASE_URL,
)


def merge_into_paragraphs(segments: list[dict], use_llm: bool = True) -> list[dict]:
    """将 ASR 片段合并为自然段落。

    优先使用大模型进行语义分析。当 use_llm=False 或未配置 API 密钥时，
    回退到基于 PARAGRAPH_GAP_THRESHOLD 的时间间隔合并。

    段落字典包含：start, end, text, seq_index。
    """
    if not segments:
        return []

    if use_llm and ANTHROPIC_API_KEY:
        return _llm_merge(segments)
    return _timegap_merge(segments)


def _timegap_merge(
    segments: list[dict],
    threshold: float | None = None,
) -> list[dict]:
    """根据时间间隔阈值合并片段。"""
    thresh = threshold if threshold is not None else PARAGRAPH_GAP_THRESHOLD

    paragraphs = []
    current = {
        "start": segments[0]["start"],
        "end": segments[0]["end"],
        "text": segments[0]["text"],
    }

    for seg in segments[1:]:
        gap = seg["start"] - current["end"]
        if gap <= thresh:
            current["end"] = seg["end"]
            current["text"] += seg["text"]
        else:
            paragraphs.append(current)
            current = {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
            }

    paragraphs.append(current)

    for i, p in enumerate(paragraphs):
        p["seq_index"] = i

    return paragraphs


def _call_llm(prompt: str, max_tokens: int = 2000) -> str:
    """调用兼容 Anthropic 格式的 LLM API。"""
    import anthropic

    kwargs = {"api_key": ANTHROPIC_API_KEY}
    if ANTHROPIC_BASE_URL:
        kwargs["base_url"] = ANTHROPIC_BASE_URL
    client = anthropic.Anthropic(**kwargs)

    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _llm_merge(segments: list[dict]) -> list[dict]:
    """使用大模型分析语义，合并为自然段落。

    当片段数量超过 50 时，先用宽松阈值预分组以降低 API 调用开销，
    再对每个多片段组进行 LLM 精分。
    """
    if len(segments) > 50:
        pre_groups = _timegap_merge(segments, threshold=10.0)
        result = []
        for group in pre_groups:
            refined = _llm_merge_group_segments(
                segments,
                group["start"],
                group["end"],
            )
            result.extend(refined)
        for i, p in enumerate(result):
            p["seq_index"] = i
        return result

    return _llm_merge_group_segments(segments, segments[0]["start"], segments[-1]["end"])


def _llm_merge_group_segments(
    all_segments: list[dict],
    group_start: float,
    group_end: float,
) -> list[dict]:
    """从 all_segments 中筛选出 [group_start, group_end] 范围的片段，调用 LLM 合并。"""
    indices = [
        i for i, s in enumerate(all_segments)
        if s["start"] >= group_start and s["end"] <= group_end
    ]
    if not indices:
        return []

    group_segs = [all_segments[i] for i in indices]
    return _llm_merge_group(group_segs)


def _llm_merge_group(segments: list[dict]) -> list[dict]:
    """对一组片段调用 LLM 进行语义段落划分，滤除与主题无关的片头片尾内容。"""
    if not segments:
        return []

    lines = []
    for i, seg in enumerate(segments):
        text_preview = seg["text"][:80].replace("\n", " ")
        lines.append(f"[{i}] \"{text_preview}\"")

    segment_text = "\n".join(lines)

    prompt = (
        "你是一个视频字幕分段专家。请分析以下 ASR 识别片段，完成两项任务：\n\n"
        "任务一：识别哪些片段属于视频的主题内容（正文），"
        "哪些属于无关的片头、片尾、过渡、开场白、赞助口播等，丢弃无关片段。\n"
        "任务二：将保留的主题片段按语义完整性、话题转换合并为自然段落。\n\n"
        "规则：\n"
        "1. 保持片段原有的顺序，不能打乱\n"
        "2. 每个段落包含至少1个连续保留的片段\n"
        "3. 语义完整的地方断开（话题转换、完整句子结束等）\n"
        "4. 只输出方括号格式，不要任何解释或额外文字\n"
        "5. 被丢弃的片段不要出现在输出中\n\n"
        "输出格式示例（丢弃了 [0] 和 [5] 两个无关片段）：\n"
        "[1-2]\n"
        "[3-4]\n\n"
        f"片段列表：\n{segment_text}\n\n"
        "合并后的段落："
    )

    try:
        result = _call_llm(prompt, max_tokens=2000)
    except Exception:
        return _timegap_merge(segments)

    groups = re.findall(r"\[(\d+)-(\d+)\]", result)
    if not groups:
        return _timegap_merge(segments)

    # 收集所有被引用的索引
    mentioned = set()
    for start_str, end_str in groups:
        s, e = int(start_str), int(end_str)
        mentioned.update(range(s, e + 1))

    if not mentioned:
        return _timegap_merge(segments)

    paragraphs = []
    for start_str, end_str in groups:
        start_idx = int(start_str)
        end_idx = int(end_str)
        if start_idx < 0 or end_idx >= len(segments) or start_idx > end_idx:
            continue
        group_segs = [segments[i] for i in range(start_idx, end_idx + 1)]
        paragraphs.append({
            "start": group_segs[0]["start"],
            "end": group_segs[-1]["end"],
            "text": "".join(s["text"] for s in group_segs),
        })

    if not paragraphs:
        return _timegap_merge(segments)

    for i, p in enumerate(paragraphs):
        p["seq_index"] = i

    return paragraphs
