"""ffmpeg 操作统一封装：音频提取、人声分离、视频裁剪、拼接、元数据。"""

import json
import os
import subprocess
from pathlib import Path

from moviepy import ImageClip, VideoFileClip, concatenate_videoclips

from src.config import get_config, BASE_DIR
from src.logger import default_logger as logger
from src.utils import ensure_date_dir

# ── 音频相关 ──
ffmpeg_prefix = f"{BASE_DIR}/bin/"


def extract_audio(video_path: str, audio_path: str | None = None) -> str:
    """使用 ffmpeg 从视频中提取音频。

    返回提取的 WAV 音频文件路径。
    """
    video_path = Path(video_path)
    if audio_path is None:
        audio_path = str(ensure_date_dir(get_config("source_dir"), f"{video_path.stem}_audio.wav"))

    cmd = [
        f"{ffmpeg_prefix}ffmpeg", "-i", str(video_path),
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
        f"{ffmpeg_prefix}ffmpeg", "-i", str(audio_path),
        "-af", "pan=mono|c0=FL+FR,highpass=f=200,lowpass=f=4000",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def remove_vocals(audio_path: str, output_path: str | None = None) -> str:
    """使用 ffmpeg 去除人声（保留背景音乐）。

    原理：声道相消（karaoke），利用人声通常位于中央声道的特点，
    将左右声道相减以抵消中央人声，保留两侧乐器声。
    返回处理后的音频文件路径。
    """
    if output_path is None:
        p = Path(audio_path)
        output_path = str(p.parent / f"{p.stem}_instrumental{p.suffix}")

    cmd = [
        f"{ffmpeg_prefix}ffmpeg", "-i", str(audio_path),
        "-af", "pan=stereo|c0=c0-c1|c1=c1-c0",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


# ── 视频裁剪 ──

def split_video_clip(
        video_path: str,
        vocals_path: str,
        start: float,
        end: float,
        output_path: str,
        crop: str | None = None,
        no_audio: bool = False,
) -> str:
    """按时间范围分割视频片段，并使用分离后人声作为音轨。

    将原视频画面与处理后的人声音轨合并输出。
    若 no_audio=True，则输出不含音轨的纯视频片段。
    crop: ffmpeg crop 表达式，如 "1280:610:0:0"（裁掉底部 110px）
    """
    cmd = [
        f"{ffmpeg_prefix}ffmpeg",
        "-ss", str(start), "-to", str(end),
        "-i", str(video_path),
    ]
    if no_audio:
        cmd += ["-c:v", "libx264", "-crf", "18", "-an", "-y", str(output_path)]
    else:
        cmd += [
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


def split_video_segment(video_path: str, start: float, end: float, output_path: str) -> bool:
    """简单裁剪视频片段（无音频处理）。"""
    cmd = [
        f"{ffmpeg_prefix}ffmpeg",
        "-ss", str(start), "-to", str(end),
        "-i", str(video_path),
        "-c", "copy",
        "-y", str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


# ── 视频元数据 ──

def get_video_duration(video_path: str) -> float:
    """使用 ffprobe 获取视频时长（秒）。"""
    cmd = [
        f"{ffmpeg_prefix}ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"获取视频元数据 {e}")
        return 0.0


def get_video_metadata(video_path: str) -> dict:
    """使用 ffprobe 获取视频分辨率、帧率等元数据。

    返回：
        {
            "frame_width": int,
            "frame_height": int,
            "frame_rate": float,
        }
    """
    cmd = [
        f"{ffmpeg_prefix}ffprobe", "-v", "error", "-print_format", "json",
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


# ── 视频拼接 ──
def _resize_to_cover(clip, target_w: int, target_h: int):
    """缩放+居中裁剪使 clip 完全填充目标尺寸（object-fit: cover 语义）。"""
    w, h = clip.size
    if w == target_w and h == target_h:
        return clip
    scale = max(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = clip.resized(new_size=(new_w, new_h))
    x1 = (new_w - target_w) // 2
    y1 = (new_h - target_h) // 2
    return resized.cropped(x1=x1, y1=y1, width=target_w, height=target_h)


def concat_videos_by_movie(
    clip_paths: list[str],
    output_path: str,
    target_width: int | None = None,
    target_height: int | None = None,
) -> str:
    clips = []
    for file in clip_paths:
        if file.endswith(('.jpg', '.png', '.jpeg')):
            # 加载图片，并设置每张图片的显示时长为2秒
            clip = ImageClip(file).with_duration(2)
        elif file.endswith(('.mp4', '.avi', '.mov')):
            # 加载视频文件
            clip = VideoFileClip(file)
        else:
            continue

        if target_width and target_height:
            clip = _resize_to_cover(clip, target_width, target_height)
        clips.append(clip)

    if not clips:
        raise ValueError("没有可拼接的素材片段")

    # 将所有的剪辑片段按顺序拼接
    final_video = concatenate_videoclips(clips)

    # 从首个视频片段获取帧率，默认 24
    fps = 24
    for c in clips:
        if hasattr(c, 'fps') and c.fps:
            fps = c.fps
            break

    # 输出最终的视频文件
    final_video.write_videofile(output_path, fps=fps)
    return output_path


def mix_audio_tracks(video_path: str, audio_paths: list[str], output_path: str | None = None) -> str:
    """将多个音频文件混入视频中（保留原视频音轨并叠加音频素材）。

    参数：
        video_path: 输入视频路径（已拼接好的视频）。
        audio_paths: 音频文件路径列表（如背景音乐、音效）。
        output_path: 输出视频路径（为 None 时自动生成）。

    返回输出视频路径。
    """
    if not audio_paths:
        return video_path

    from pathlib import Path
    vp = Path(video_path)
    if output_path is None:
        from src.utils import ensure_date_dir
        from src.config import get_config
        output_path = str(ensure_date_dir(get_config("mixed_dir"), f"{vp.stem}_mixed{vp.suffix}"))

    out = Path(output_path)
    tmp = out.with_suffix(".tmp.mp4")

    import subprocess

    # 提前探测视频是否有音轨，避免 ffmpeg 因缺失音轨崩溃
    has_audio = True
    try:
        probe = subprocess.run(
            [f"{ffmpeg_prefix}ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(vp)],
            capture_output=True, text=True, timeout=30,
        )
        has_audio = probe.stdout.strip() == "audio"
    except Exception:
        has_audio = True  # 探测失败时假设有音轨

    if has_audio:
        # 视频有音轨：视频音频 + 音频素材混合
        n_inputs = 1 + len(audio_paths)
        inputs = ["-i", str(vp)]
        for ap in audio_paths:
            inputs += ["-i", str(ap)]
        filter_parts = [f"[{i}:a]" for i in range(n_inputs)]
        filter_str = "".join(filter_parts) + f"amix=inputs={n_inputs}:duration=first[aud]"
    else:
        # 视频无音轨：仅混合音频素材
        n_inputs = len(audio_paths)
        inputs = ["-i", str(vp)]
        for ap in audio_paths:
            inputs += ["-i", str(ap)]
        filter_parts = [f"[{i+1}:a]" for i in range(n_inputs)]
        filter_str = "".join(filter_parts) + f"amix=inputs={n_inputs}:duration=first[aud]"

    cmd = [
        f"{ffmpeg_prefix}ffmpeg",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "0:v",
        "-map", "[aud]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        "-y", str(tmp),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception:
        raise

    if out.exists():
        out.unlink()
    tmp.rename(out)
    return str(out)


def concat_videos(
    clip_paths: list[str],
    output_path: str,
    target_width: int | None = None,
    target_height: int | None = None,
) -> str:
    """将多个视频片段直接拼接（无转场），使用 concat demuxer 流复制。

    所有片段需具有相同的编解码参数，否则 ffmpeg 会报错。
    """
    logger.debug("拼接素材: %s", clip_paths)
    n = len(clip_paths)
    if n == 0:
        raise ValueError("No clips to concatenate")

    output = Path(output_path).resolve()
    logger.info("输出路径: %s", output)
    if not output.suffix:
        raise ValueError(f"输出路径缺少文件扩展名: {output_path}")

    list_path = output.with_suffix(".concat.txt")

    output.parent.mkdir(parents=True, exist_ok=True)

    if n == 1:
        import shutil
        shutil.copy2(clip_paths[0], str(output))
        return str(output)

    # 过滤不存在的文件
    valid_paths = [p for p in clip_paths if Path(p).exists()]
    if not valid_paths:
        raise FileNotFoundError("所有素材文件均不存在")
    clip_paths = valid_paths

    # 如果包含图片文件，降级为 MoviePy 方式（ffmpeg concat demuxer 无法正确处理图片 DAR）
    if any(p.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')) for p in clip_paths):
        logger.info("检测到图片素材，使用 MoviePy 拼接")
        return concat_videos_by_movie(clip_paths, str(output), target_width, target_height)

    # 创建临时文件列表（绝对路径）
    print(f"多媒体文本列表{list_path}")
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for p in clip_paths:
                if p.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    # 图片需要指定持续时间，这里设为2秒
                    # 注意：duration 必须紧跟在 file 行之后
                    f.write(f"file '{Path(p).resolve().as_posix()}'\n")
                    f.write(f"duration 2\n")
                else:
                    f.write(f"file '{Path(p).resolve().as_posix()}'\n")

        cmd = [
            f"{ffmpeg_prefix}ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-fflags", "+genpts",
            "-c:v", "libx264",  # 视频编码
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1:1",
            str(output)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = result.stderr[-1200:] if result.stderr else "(no stderr)"
            raise RuntimeError(
                f"ffmpeg concat 失败 (exit {result.returncode}):\n"
                f"cmd: {' '.join(cmd)}\n"
                f"{stderr}"
            )
    finally:
        list_path.unlink(missing_ok=True)

    return str(output)


# ── 字幕压制 ──

def composite_subtitles(video_path: str, srt_path: str, output_path: str | None = None) -> str:
    """使用 ffmpeg 将字幕压制到视频中。"""
    video_path = Path(video_path)
    if output_path is None:
        output_path = str(ensure_date_dir(get_config("mixed_dir"), f"{video_path.stem}_subtitled{video_path.suffix}"))

    srt_filter_path = str(Path(srt_path).as_posix())

    cmd = [
        f"{ffmpeg_prefix}ffmpeg", "-i", str(video_path),
        "-vf", f"subtitles={srt_filter_path}:force_style='FontName=Noto Sans SC,FontSize=18,Alignment=2'",
        "-c:a", "copy",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
