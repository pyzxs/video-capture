"""基于时间间隔或智能体分析的段落合并。"""

import re

from src.services.agents import call_agent
from src.config import get_config


def merge_into_paragraphs(segments: list[dict], use_llm: bool = True) -> list[dict]:
    """将 ASR 片段合并为自然段落。

    优先使用智能体「字幕分段」进行语义分析。当 use_llm=False 或
    智能体未配置时，回退到基于 paragraph_gap_threshold 的时间间隔合并。

    段落字典包含：start, end, text, seq_index。
    """
    if not segments:
        return []

    if use_llm:
        try:
            return _llm_merge(segments)
        except Exception:
            return _timegap_merge(segments)
    return _timegap_merge(segments)


def _timegap_merge(
    segments: list[dict],
    threshold: float | None = None,
) -> list[dict]:
    """根据时间间隔阈值合并片段。"""
    thresh = threshold if threshold is not None else get_config("paragraph_gap_threshold")

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


def _llm_merge(segments: list[dict]) -> list[dict]:
    """使用智能体分析语义，合并为自然段落。

    当片段数量超过 50 时，先用宽松阈值预分组以降低 API 调用开销，
    再对每个多片段组进行智能体精分。
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
    """从 all_segments 中筛选出 [group_start, group_end] 范围的片段，调用智能体合并。"""
    indices = [
        i for i, s in enumerate(all_segments)
        if s["start"] >= group_start and s["end"] <= group_end
    ]
    if not indices:
        return []

    group_segs = [all_segments[i] for i in indices]
    return _llm_merge_group(group_segs)


def _llm_merge_group(segments: list[dict]) -> list[dict]:
    """对一组片段调用智能体进行语义段落划分，滤除无关内容。"""
    if not segments:
        return []

    lines = []
    for i, seg in enumerate(segments):
        text_preview = seg["text"][:80].replace("\n", " ")
        lines.append(f"[{i}] \"{text_preview}\"")

    user_message = "\n".join(lines)

    result = call_agent("str_sem", user_message, max_tokens=2000)

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
