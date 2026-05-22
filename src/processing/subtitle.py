"""字幕处理：解析 SRT/ASS、软字幕提取、时间轴统一获取。"""

import json
import re
import subprocess
from pathlib import Path

from src.config import get_config
from src.logger import default_logger as logger
from src.processing.asr import transcribe
from src.processing.ffmpeg import extract_audio
from src.utils import ensure_date_dir, ts_to_seconds, get_ffmpeg_path, get_ffprobe_path, _CREATIONFLAGS

_ffmpeg_bin = get_ffmpeg_path()
_ffprobe_bin = get_ffprobe_path()


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


def _ffmpeg_stream_info(video_path: str) -> list[dict]:
    """通过 ffprobe 返回所有字幕流信息。"""
    cmd = [
        _ffprobe_bin, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "s",
        str(video_path),
    ]
    result = subprocess.run(cmd, creationflags=_CREATIONFLAGS, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return data.get("streams", [])


def extract_soft_subtitles(video_path: str) -> list[dict] | None:
    """尝试通过 ffmpeg 提取嵌入的软字幕流。

    支持 SRT（subrip）和 ASS/SSA 格式。返回包含 ``start``、
    ``end``、``text`` 键的片段字典列表（与 ASR 输出格式一致），
    如果没有可用的字幕流则返回 ``None``。
    """
    streams = _ffmpeg_stream_info(video_path)
    if not streams:
        return None

    # 选择第一个字幕流（优先 subrip，其次 ass）
    idx = None
    codec = None
    for s in streams:
        c = s.get("codec_name", "")
        if c in ("subrip", "srt"):
            idx = s["index"]
            codec = c
            break
    if idx is None:
        for s in streams:
            c = s.get("codec_name", "")
            if c in ("ass", "ssa"):
                idx = s["index"]
                codec = c
                break
    if idx is None:
        return None

    stem = Path(video_path).stem
    ext = ".srt" if codec in ("subrip", "srt") else ".ass"
    sub_path = str(ensure_date_dir(get_config("material_dir"), f"{stem}_subs{ext}"))

    cmd = [
        _ffmpeg_bin, "-i", str(video_path),
        "-map", f"0:{idx}",
        "-y", sub_path,
    ]
    subprocess.run(cmd, creationflags=_CREATIONFLAGS, check=True, capture_output=True)

    segments = parse_subtitles(sub_path, ext)
    return segments if segments else None


def get_timestamps(video_path: str, language: str = "zh") -> list[dict]:
    """统一时间轴提取。

    优先尝试提取软字幕。如果没有嵌入式字幕则回退到
    音频提取 + ASR（Whisper）。
    """
    segments = extract_soft_subtitles(video_path)
    if segments:
        logger.info("  → 提取到 %d 个字幕片段（软字幕）", len(segments))
        return segments

    logger.info("  → 未找到软字幕，回退到 ASR...")
    audio_path = extract_audio(video_path)
    return transcribe(audio_path, language=language)
