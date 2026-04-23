"""统一时间轴提取：优先软字幕，回退到 ASR。"""

import json
import re
import subprocess
from pathlib import Path

from src.config import OUTPUT_DIR
from src.processing.asr import transcribe
from src.processing.video import extract_audio
from src.utils import parse_subtitles


def _ffmpeg_stream_info(video_path: str) -> list[dict]:
    """通过 ffprobe 返回所有字幕流信息。"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "s",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
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

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(video_path).stem
    ext = ".srt" if codec in ("subrip", "srt") else ".ass"
    sub_path = str(OUTPUT_DIR / f"{stem}_subs{ext}")

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-map", f"0:{idx}",
        "-y", sub_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    segments = parse_subtitles(sub_path, ext)
    return segments if segments else None


def _parse_subtitles(path: str, fmt: str) -> list[dict]:
    """解析 SRT 或 ASS 文件为片段字典列表。"""
    from src.utils import parse_subtitles as _ps
    return _ps(path, fmt)


_TIMESTAMP_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def _ts_to_seconds(ts: str) -> float:
    from src.utils import ts_to_seconds
    return ts_to_seconds(ts)


def get_timestamps(video_path: str, language: str = "zh") -> list[dict]:
    """统一时间轴提取。

    优先尝试提取软字幕。如果没有嵌入式字幕则回退到
    音频提取 + ASR（Whisper）。
    """
    segments = extract_soft_subtitles(video_path)
    if segments:
        print(f"  → 提取到 {len(segments)} 个字幕片段（软字幕）")
        return segments

    print(f"  → 未找到软字幕，回退到 ASR...")
    audio_path = extract_audio(video_path)
    return transcribe(audio_path, language=language)
