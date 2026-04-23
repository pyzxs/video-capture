"""纯工具函数：时间格式转换、SRT/ASS 字幕解析。"""

import re
from pathlib import Path


_TIMESTAMP_RE = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d+)"
)


def ts_to_seconds(ts: str) -> float:
    """将 SRT/ASS 时间戳转换为秒数。

    支持格式：
      - SRT:  00:00:01,000  (时=2位, 毫秒=3位)
      - ASS:  0:00:01.00    (时=1位, 厘秒=2位)
    """
    m = _TIMESTAMP_RE.match(ts)
    if not m:
        return 0.0
    h, mi, s, ms_part = int(m[1]), int(m[2]), int(m[3]), m[4]
    # ASS 厘秒（2位）→ 毫秒（3位），SRT 已是毫秒
    if len(ms_part) == 2:
        ms = int(ms_part) * 10
    else:
        ms = int(ms_part)
    return h * 3600 + mi * 60 + s + ms / 1000


def format_time(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳（HH:MM:SS,mmm）。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = round((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(path: str | Path) -> list[dict]:
    """解析 SRT 字幕文件为片段列表。

    每项包含：start, end, text。
    """
    segments = []
    with open(path, encoding="utf-8-sig") as f:
        content = f.read()

    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        time_line = lines[1] if "-->" in lines[1] else None
        if not time_line:
            continue
        parts = time_line.split(" --> ")
        if len(parts) != 2:
            continue
        start = ts_to_seconds(parts[0].strip())
        end = ts_to_seconds(parts[1].strip())
        text = "\n".join(lines[2:]).strip()
        text = re.sub(r"<[^>]+>", "", text)  # 去除 HTML 标签
        text = text.replace("\n", " ")
        if text:
            segments.append({"start": start, "end": end, "text": text})

    return segments


def parse_ass(path: str | Path) -> list[dict]:
    """解析 ASS 字幕文件为片段列表。

    每项包含：start, end, text。
    """
    segments = []
    with open(path, encoding="utf-8-sig") as f:
        content = f.read()

    in_events = False
    format_line = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("[Events]"):
            in_events = True
            continue
        if not in_events:
            continue
        if line.startswith("Format:"):
            format_line = [c.strip() for c in line[7:].split(",")]
            continue
        if not line.startswith("Dialogue:"):
            continue

        parts = line.split(",", len(format_line) - 1) if format_line else None
        if not parts or len(parts) < 4:
            continue

        start = ts_to_seconds(parts[1].strip())
        end = ts_to_seconds(parts[2].strip())
        text = parts[-1].strip()
        text = re.sub(r"\{[^}]*}", "", text)  # 去除 ASS 样式标签
        text = text.replace("\\N", " ").replace("\\n", " ")
        if text:
            segments.append({"start": start, "end": end, "text": text})

    return segments


def parse_subtitles(path: str | Path, fmt: str = ".srt") -> list[dict]:
    """解析 SRT 或 ASS 文件为片段字典列表。"""
    if fmt == ".ass":
        return parse_ass(path)
    return parse_srt(path)
