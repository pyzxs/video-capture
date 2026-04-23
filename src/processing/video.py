import json
import subprocess
from pathlib import Path

from src.config import OUTPUT_DIR


def extract_audio(video_path: str, audio_path: str | None = None) -> str:
    """使用 ffmpeg 从视频中提取音频。

    返回提取的 WAV 音频文件路径。
    """
    video_path = Path(video_path)
    if audio_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        audio_path = str(OUTPUT_DIR / f"{video_path.stem}_audio.wav")

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        "-y", str(audio_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return audio_path


def separate_vocals(audio_path: str, output_path: str | None = None) -> str:
    """使用 ffmpeg 隔离人声（去除背景音乐）。

    原理：中心声道提取 + 带通滤波（200-4000Hz 人声频段）。
    返回处理后的音频文件路径。
    """
    if output_path is None:
        p = Path(audio_path)
        output_path = str(p.parent / f"{p.stem}_vocals{p.suffix}")

    cmd = [
        "ffmpeg", "-i", str(audio_path),
        "-af", "pan=mono|c0=FL+FR,highpass=f=200,lowpass=f=4000",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def split_video_clip(
    video_path: str,
    vocals_path: str,
    start: float,
    end: float,
    output_path: str,
    crop: str | None = None,
) -> str:
    """按时间范围分割视频片段，并使用分离后人声作为音轨。

    将原视频画面与处理后的人声音轨合并输出。
    crop: ffmpeg crop 表达式，如 "1280:610:0:0"（裁掉底部 110px）
    """
    cmd = [
        "ffmpeg",
        "-ss", str(start), "-to", str(end),
        "-i", str(video_path),
        "-ss", str(start), "-to", str(end),
        "-i", str(vocals_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
    ]
    if crop:
        cmd += ["-vf", f"crop={crop}"]
    cmd += [
        "-c:v", "libx264", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def get_video_duration(video_path: str) -> float:
    """使用 ffprobe 获取视频时长（秒）。"""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def get_video_metadata(video_path: str) -> dict:
    """使用 ffprobe 获取视频分辨率、帧率等元数据。

    返回：
        {
            "frame_width": int,
            "frame_height": int,
            "frame_rate": float,
            "duration": float,
        }
    """
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-select_streams", "v:0",
        str(video_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        return {"frame_width": 0, "frame_height": 0, "frame_rate": 0.0}

    s = streams[0]
    w = s.get("width", 0)
    h = s.get("height", 0)
    avg_fps = s.get("avg_frame_rate", "0/1")
    if "/" in avg_fps:
        num, den = avg_fps.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    else:
        fps = float(avg_fps)

    return {"frame_width": w, "frame_height": h, "frame_rate": round(fps, 3)}
