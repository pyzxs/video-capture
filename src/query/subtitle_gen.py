from src.utils import format_time as _format_time


def generate_srt(optimized_text: str, paragraphs: list[dict]) -> str:
    """根据优化后的文本和原始时间生成 SRT 字幕内容。

    参数：
        optimized_text: LLM 优化后的字幕文本。
        paragraphs: 包含 start_time/end_time 的段落字典列表。

    返回：
        SRT 格式字符串。
    """
    srt_lines = []

    if not paragraphs:
        return ""

    if len(paragraphs) == 1:
        srt_lines.append("1")
        p = paragraphs[0]
        srt_lines.append(
            f"{_format_time(p['start_time'])} --> {_format_time(p['end_time'])}"
        )
        srt_lines.append(optimized_text)
        srt_lines.append("")
        return "\n".join(srt_lines)

    total_duration = sum(p["end_time"] - p["start_time"] for p in paragraphs)
    char_ratio = len(optimized_text) / total_duration if total_duration > 0 else 0

    chars_used = 0
    for i, p in enumerate(paragraphs):
        para_duration = p["end_time"] - p["start_time"]
        if i < len(paragraphs) - 1:
            para_chars = max(1, int(para_duration * char_ratio))
        else:
            para_chars = len(optimized_text) - chars_used

        para_text = optimized_text[chars_used: chars_used + para_chars].strip()
        chars_used += para_chars

        if para_text:
            srt_lines.append(str(i + 1))
            srt_lines.append(
                f"{_format_time(p['start_time'])} --> {_format_time(p['end_time'])}"
            )
            srt_lines.append(para_text)
            srt_lines.append("")

    return "\n".join(srt_lines)


def save_srt(srt_content: str, output_path: str):
    """将 SRT 内容写入文件。"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
