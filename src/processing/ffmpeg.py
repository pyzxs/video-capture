"""ffmpeg 操作统一封装：音频提取、人声分离、视频裁剪、拼接、元数据。"""

import json
import os
import subprocess
import sys
from pathlib import Path

from moviepy import ImageClip, VideoFileClip, concatenate_videoclips

from src.config import get_config, BASE_DIR
from src.logger import default_logger as logger
from src.utils import ensure_date_dir

# Windows 下隐藏 ffmpeg/ffprobe 子进程的控制台窗口
_CREATIONFLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _run(cmd, **kwargs):
    """subprocess.run 包装，Windows 下自动隐藏控制台窗口。"""
    kwargs.setdefault("creationflags", _CREATIONFLAGS)
    return subprocess.run(cmd, **kwargs)


# ── bin 路径：打包后用 exe 同级目录下的 bin/，开发时用项目根下的 bin/ ──
if getattr(sys, 'frozen', False):
    _bin_dir = Path(sys.executable).parent / "bin"
else:
    _bin_dir = Path(BASE_DIR) / "bin"

if sys.platform == "win32":
    FFMPEG = str(_bin_dir / "ffmpeg.exe")
    FFPROBE = str(_bin_dir / "ffprobe.exe")
else:
    FFMPEG = str(_bin_dir / "ffmpeg")
    FFPROBE = str(_bin_dir / "ffprobe")

# 兼容旧代码的 ffmpeg_prefix（外部模块仍在使用）
ffmpeg_prefix = str(_bin_dir) + "/"

print(f"音频处理工具地址: {_bin_dir}")


# ── 硬件编码器检测（启动时探测一次，缓存结果） ──

def _detect_hw_encoder() -> list[str]:
    """探测可用的 H.264 硬件编码器，返回 ffmpeg 编码参数列表。"""
    candidates = [
        # NVIDIA NVENC
        ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "18"],
        # Intel QSV
        ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "18"],
        # AMD AMF
        ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "18", "-qp_p", "18"],
    ]
    for params in candidates:
        try:
            cmd = [
                FFMPEG, "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1",
                *params, "-frames:v", "1",
                "-f", "null", "-y", os.devnull,
            ]
            _run(cmd, check=True, capture_output=True)
            return params
        except (subprocess.CalledProcessError, OSError):
            continue
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "18"]


_HW_ENCODER: list[str] | None = None


def _get_encoder() -> list[str]:
    global _HW_ENCODER
    if _HW_ENCODER is None:
        _HW_ENCODER = _detect_hw_encoder()
        encoder_name = _HW_ENCODER[1] if len(_HW_ENCODER) > 1 else "unknown"
        logger.info(f"视频编码器: {encoder_name}")
    return _HW_ENCODER


def extract_audio(video_path: str, audio_path: str | None = None) -> str:
    """使用 ffmpeg 从视频中提取音频。

    返回提取的 WAV 音频文件路径。
    """
    video_path = Path(video_path)
    if video_path.suffix == ".part":
        raise FileNotFoundError(f"视频文件未下载完成（.part 文件）: {video_path}")
    if not video_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    if audio_path is None:
        audio_path = str(ensure_date_dir(get_config("source_dir"), f"{video_path.stem}_audio.wav"))

    cmd = [
        FFMPEG, "-i", str(video_path),
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        "-y", str(audio_path),
    ]
    _run(cmd, check=True, capture_output=True)
    return audio_path


def compress_audio_for_asr(audio_path: str) -> str:
    """将音频压缩为 mp3 格式以减少上传体积（约缩小 4-5 倍）。

    ASR 模型对 64kbps mono mp3 识别效果无损失。
    如果压缩失败则返回原始路径。
    """
    audio_path = Path(audio_path)
    if audio_path.suffix == ".mp3":
        return str(audio_path)

    mp3_path = audio_path.with_suffix(".mp3")
    cmd = [
        FFMPEG, "-i", str(audio_path),
        "-vn", "-ar", "16000", "-ac", "1",
        "-b:a", "64k",
        "-y", str(mp3_path),
    ]
    try:
        _run(cmd, check=True, capture_output=True)
        return str(mp3_path)
    except subprocess.CalledProcessError:
        return str(audio_path)


def separate_vocals(audio_path: str, output_path: str | None = None) -> str:
    """使用 ffmpeg 隔离人声（去除背景音乐）。

    原理：中心声道提取 + 带通滤波（200-4000Hz 人声频段）。
    返回处理后的音频文件路径。
    """
    if output_path is None:
        p = Path(audio_path)
        output_path = str(p.parent / f"{p.stem}_vocals{p.suffix}")

    cmd = [
        FFMPEG, "-i", str(audio_path),
        "-af", "pan=mono|c0=FL+FR,highpass=f=200,lowpass=f=4000",
        "-y", str(output_path),
    ]
    _run(cmd, check=True, capture_output=True)
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
        FFMPEG, "-i", str(audio_path),
        "-af", "pan=stereo|c0=c0-c1|c1=c1-c0",
        "-y", str(output_path),
    ]
    _run(cmd, check=True, capture_output=True)
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
    enc = _get_encoder()
    cmd = [
        FFMPEG,
        "-ss", str(start), "-to", str(end),
        "-i", str(video_path),
    ]
    if no_audio:
        if crop:
            cmd += ["-vf", f"crop={crop}"]
        cmd += [*enc, "-an", "-y", str(output_path)]
    elif vocals_path and Path(vocals_path).exists():
        cmd += [
            "-ss", str(start), "-to", str(end),
            "-i", str(vocals_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
        ]
        if crop:
            cmd += ["-vf", f"crop={crop}"]
        cmd += [
            *enc,
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-y", str(output_path),
        ]
    else:
        cmd += [
            "-map", "0:v:0",
            "-map", "0:a:0",
        ]
        if crop:
            cmd += ["-vf", f"crop={crop}"]
        cmd += [
            *enc,
            "-c:a", "aac", "-b:a", "192k",
            "-y", str(output_path),
        ]
    _run(cmd, check=True, capture_output=True)
    return output_path


def split_clip_and_extract_audio(
        video_path: str,
        start: float,
        end: float,
        video_output: str,
        audio_output: str,
        no_audio: bool = False,
) -> str:
    """一次 ffmpeg 调用同时输出视频片段和 ASR 用音频，减少磁盘 I/O。"""
    enc = _get_encoder()
    cmd = [
        FFMPEG,
        "-ss", str(start), "-to", str(end),
        "-i", str(video_path),
    ]
    if no_audio:
        cmd += [*enc, "-an", "-y", str(video_output)]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a:0", *enc,
                "-c:a", "aac", "-b:a", "192k", "-y", str(video_output)]
    cmd += ["-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-y", str(audio_output)]
    _run(cmd, check=True, capture_output=True)
    return video_output


def split_video_segment(video_path: str, start: float, end: float, output_path: str) -> bool:
    """简单裁剪视频片段（无音频处理）。"""
    cmd = [
        FFMPEG,
        "-ss", str(start), "-to", str(end),
        "-i", str(video_path),
        "-c", "copy",
        "-y", str(output_path),
    ]
    try:
        _run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


# ── 视频元数据 ──

def get_video_info(video_path: str) -> dict:
    """使用单次 ffprobe 调用获取视频时长、分辨率、帧率等元数据。

    返回：
        {
            "duration": float,
            "frame_width": int,
            "frame_height": int,
            "frame_rate": float,
        }
    """
    cmd = [
        FFPROBE, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", "-select_streams", "v:0",
        str(video_path),
    ]
    try:
        result = _run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error("ffprobe 获取视频信息失败: %s", e)
        return {"duration": 0.0, "frame_width": 0, "frame_height": 0, "frame_rate": 0.0}

    data = json.loads(result.stdout)

    duration = 0.0
    fmt = data.get("format", {})
    try:
        duration = float(fmt.get("duration", 0))
    except (ValueError, TypeError):
        pass

    streams = data.get("streams", [])
    if not streams:
        return {"duration": duration, "frame_width": 0, "frame_height": 0, "frame_rate": 0.0}

    s = streams[0]
    w = s.get("width", 0)
    h = s.get("height", 0)
    avg_fps = s.get("avg_frame_rate", "0/1")
    if "/" in avg_fps:
        num, den = avg_fps.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    else:
        fps = float(avg_fps)

    return {"duration": duration, "frame_width": w, "frame_height": h, "frame_rate": round(fps, 3)}


def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）。"""
    return get_video_info(video_path)["duration"]


def get_video_metadata(video_path: str) -> dict:
    """获取视频分辨率、帧率等元数据（兼容旧接口）。"""
    info = get_video_info(video_path)
    return {"frame_width": info["frame_width"], "frame_height": info["frame_height"], "frame_rate": info["frame_rate"]}


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


def mix_audio_tracks(video_path: str, audio_paths: list[str], output_path: str | None = None, bg_volume: float = 1.0) -> str:
    """将多个音频文件混入视频中（保留原视频音轨并叠加音频素材）。

    参数：
        video_path: 输入视频路径（已拼接好的视频）。
        audio_paths: 音频文件路径列表（如背景音乐、音效）。
        output_path: 输出视频路径（为 None 时自动生成）。
        bg_volume: 背景音频音量系数（0.0~1.0），默认 1.0 不衰减。

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
        probe = _run(
            [FFPROBE, "-v", "error", "-select_streams", "a:0",
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
        if bg_volume < 1.0:
            parts = [f"[0:a]volume=1.0[a0]"]
            for i in range(len(audio_paths)):
                parts.append(f"[{i+1}:a]volume={bg_volume:.2f}[a{i+1}]")
            mix_inputs = "".join(f"[a{i}]" for i in range(n_inputs))
            filter_str = ";".join(parts) + f";{mix_inputs}amix=inputs={n_inputs}:duration=first[aud]"
        else:
            filter_parts = [f"[{i}:a]" for i in range(n_inputs)]
            filter_str = "".join(filter_parts) + f"amix=inputs={n_inputs}:duration=first[aud]"
    else:
        # 视频无音轨：仅混合音频素材
        n_inputs = len(audio_paths)
        inputs = ["-i", str(vp)]
        for ap in audio_paths:
            inputs += ["-i", str(ap)]
        if bg_volume < 1.0:
            parts = []
            for i in range(len(audio_paths)):
                parts.append(f"[{i+1}:a]volume={bg_volume:.2f}[a{i+1}]")
            mix_inputs = "".join(f"[a{i+1}]" for i in range(len(audio_paths)))
            filter_str = ";".join(parts) + f";{mix_inputs}amix=inputs={n_inputs}:duration=first[aud]"
        else:
            filter_parts = [f"[{i + 1}:a]" for i in range(n_inputs)]
            filter_str = "".join(filter_parts) + f"amix=inputs={n_inputs}:duration=first[aud]"

    cmd = [
        FFMPEG,
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
        _run(cmd, check=True, capture_output=True)
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
    if len(clip_paths) == 0:
        raise ValueError("No clips to concatenate")

    output = Path(output_path).resolve()
    logger.info("输出路径: %s", output)
    if not output.suffix:
        raise ValueError(f"输出路径缺少文件扩展名: {output_path}")

    list_path = output.with_suffix(".concat.txt")

    output.parent.mkdir(parents=True, exist_ok=True)

    # 过滤不存在或为空的文件，并验证包含有效媒体流
    valid_paths = []
    for p in clip_paths:
        pp = Path(p)
        if not pp.exists() or pp.stat().st_size == 0:
            continue
        try:
            probe = _run(
                [FFPROBE, "-v", "error", "-show_entries", "stream=codec_type",
                 "-of", "csv=p=0", str(p)],
                capture_output=True, text=True, timeout=10,
            )
            if probe.stdout.strip():
                valid_paths.append(p)
            else:
                logger.warning("concat_videos: 跳过无媒体流的文件 %s", p)
        except Exception:
            valid_paths.append(p)  # 探测失败时保留，让 ffmpeg 自行判断
    if not valid_paths:
        raise FileNotFoundError("所有素材文件均不存在或无效")
    clip_paths = valid_paths
    n = len(clip_paths)

    if n == 1:
        import shutil
        shutil.copy2(clip_paths[0], str(output))
        return str(output)

    # 如果包含图片文件，降级为 MoviePy 方式（ffmpeg concat demuxer 无法正确处理图片 DAR）
    if any(p.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')) for p in clip_paths):
        logger.info("检测到图片素材，使用 MoviePy 拼接")
        return concat_videos_by_movie(clip_paths, str(output), target_width, target_height)

    # 创建临时文件列表（绝对路径）
    print(f"多媒体文本列表{list_path}")
    try:
        with open(list_path, "w", encoding="utf-8", newline="\n") as f:
            for p in clip_paths:
                if p.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    # 图片需要指定持续时间，这里设为2秒
                    # 注意：duration 必须紧跟在 file 行之后
                    f.write(f"file '{Path(p).resolve().as_posix()}'\n")
                    f.write(f"duration 2\n")
                else:
                    f.write(f"file '{Path(p).resolve().as_posix()}'\n")

        cmd = [
            FFMPEG, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-fflags", "+genpts",
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1:1",
            str(output)
        ]
        result = _run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = result.stderr[-1200:] if result.stderr else "(no stderr)"
            # 读取 concat 列表内容以辅助排查
            try:
                concat_content = list_path.read_text(encoding="utf-8")
            except Exception:
                concat_content = "(无法读取)"
            raise RuntimeError(
                f"ffmpeg concat 失败 (exit {result.returncode}):\n"
                f"input files ({len(clip_paths)}): {clip_paths}\n"
                f"concat list:\n{concat_content}\n"
                f"cmd: {' '.join(cmd)}\n"
                f"{stderr}"
            )
    finally:
        list_path.unlink(missing_ok=True)

    return str(output)


def concat_with_audio_and_subs(
        clip_paths: list[str],
        output_path: str,
        audio_paths: list[str] | None = None,
        ass_path: str | None = None,
        target_width: int | None = None,
        target_height: int | None = None,
) -> str:
    """拼接视频 + 混音 + 字幕压制，一次 ffmpeg 调用完成（避免多次重编码）。"""
    import shutil

    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    n = len(clip_paths)
    if n == 0:
        raise ValueError("No clips to concatenate")

    audio_paths = [ap for ap in (audio_paths or []) if Path(ap).exists()]
    has_subs = ass_path and Path(ass_path).exists()

    # 单素材且无额外音轨、无字幕 → 直接复制
    if n == 1 and not audio_paths and not has_subs:
        shutil.copy2(clip_paths[0], str(output))
        return str(output)

    # 写入 concat 列表
    list_path = output.with_suffix(".concat.txt")
    with open(list_path, "w", encoding="utf-8", newline="\n") as f:
        for p in clip_paths:
            f.write(f"file '{Path(p).resolve().as_posix()}'\n")

    # 字幕文件：复制到输出目录，用纯文件名避免 Windows 盘符冒号问题
    out_dir = output.parent
    sub_name = None
    if has_subs:
        sub_dest = out_dir / Path(ass_path).name
        if str(sub_dest.resolve()) != str(Path(ass_path).resolve()):
            shutil.copy2(ass_path, sub_dest)
        sub_name = sub_dest.name

    cmd = [FFMPEG, "-y"]
    cmd += ["-f", "concat", "-safe", "0", "-i", str(list_path)]
    for ap in audio_paths:
        cmd += ["-i", str(ap)]

    # Probe source clips for audio — some clips are video-only
    has_source_audio = False
    if clip_paths:
        try:
            probe = _run(
                [FFPROBE, "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(clip_paths[0])],
                capture_output=True, text=True, timeout=10,
            )
            has_source_audio = probe.stdout.strip() == "audio"
        except Exception:
            has_source_audio = True  # probe failed, assume yes

    n_inputs = 1 + len(audio_paths)
    filters = []

    # Video chain: 字幕 → 缩放 → 输出，至少需要一个 filter
    video_filters = []
    if sub_name:
        video_filters.append(f"ass={sub_name}")
    if target_width and target_height:
        video_filters.append(
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    if not video_filters:
        video_filters.append("copy")
    chain = ",".join(video_filters)
    filters.append(f"[0:v]{chain}[v]")

    # Audio chain: 有外部音频则混音，有源音轨则直通，否则纯视频
    has_audio_output = bool(audio_paths) or has_source_audio
    if audio_paths:
        audio_labels = [f"[{i}:a]" for i in range(n_inputs)]
        filters.append("".join(audio_labels) + f"amix=inputs={n_inputs}:duration=first[a]")
    elif has_source_audio:
        filters.append("[0:a]anull[a]")

    filter_graph = ";".join(filters)
    cmd += ["-filter_complex", filter_graph]
    cmd += ["-map", "[v]"]
    if has_audio_output:
        cmd += ["-map", "[a]"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]
    if has_audio_output:
        cmd += ["-c:a", "aac"]
    cmd += ["-pix_fmt", "yuv420p"]
    cmd += ["-movflags", "+faststart"]
    cmd.append(str(output))

    try:
        result = _run(cmd, capture_output=True, text=True, cwd=str(out_dir))
        if result.returncode != 0:
            stderr = result.stderr[-1200:] if result.stderr else "(no stderr)"
            raise RuntimeError(
                f"ffmpeg concat with audio/subs failed (exit {result.returncode}):\n{stderr}"
            )
    finally:
        list_path.unlink(missing_ok=True)

    return str(output)


# ── 字幕压制 ──

def composite_subtitles(video_path: str, srt_path: str, output_path: str | None = None) -> str:
    """使用 ffmpeg 将字幕压制到视频中（支持 ASS 格式含字体样式）。"""
    import shutil
    video_path = Path(video_path)
    if output_path is None:
        output_path = str(ensure_date_dir(get_config("mixed_dir"), f"{video_path.stem}_subtitled{video_path.suffix}"))

    # 把字幕文件复制到输出目录，用纯文件名传给 ffmpeg，避开 Windows 盘符冒号问题
    out_dir = Path(output_path).parent
    sub_dest = out_dir / Path(srt_path).name
    if str(sub_dest.resolve()) != str(Path(srt_path).resolve()):
        shutil.copy2(srt_path, sub_dest)

    sub_name = sub_dest.name
    if sub_name.endswith('.ass'):
        vf = f"ass={sub_name}"
    else:
        vf = f"subtitles={sub_name}"
    cmd = [
        FFMPEG, "-i", str(video_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "copy",
        "-y", str(output_path),
    ]
    _run(cmd, check=True, capture_output=True, cwd=str(out_dir))
    return str(output_path)


# ── 视频特效 ──

EFFECT_FILTERS = {
    'gray': 'hue=s=0',
    'sepia': 'colorchannelmixer=.393:.769:.189:.349:.686:.168:.272:.534:.131',
    'bright': 'eq=brightness=0.3',
    'dark': 'eq=brightness=-0.4',
    'hcontrast': 'eq=contrast=1.6:saturation=1.1',
    'saturate': 'eq=saturation=2.0',
    'desat': 'eq=saturation=0.3',
    'vintage': 'colorchannelmixer=.393:.769:.189:.349:.686:.168:.272:.534:.131,eq=contrast=1.1:saturation=0.8',
    'cool': 'eq=saturation=1.2,hue=h=180',
    'warm': 'eq=saturation=1.4,hue=h=-30',
    'blur': 'gblur=sigma=4',
    'noir': 'hue=s=0,eq=contrast=1.4:brightness=-0.15',
    'dramatic': 'eq=contrast=1.6:brightness=-0.1:saturation=1.3',
    'soft': 'eq=brightness=0.1:contrast=0.9:saturation=0.9,gblur=sigma=0.5',
    'invert': 'negate',
    'pastel': 'eq=saturation=0.7:brightness=0.15:contrast=0.9',
    'neon': 'eq=brightness=0.2:contrast=1.5:saturation=2.5',
    'edgeglow': 'eq=brightness=0.08:contrast=1.05',
}

XFADE_MAP = {
    'crossfade': 'fade',
    'fadeblack': 'fadeblack',
    'fadewhite': 'fadewhite',
    'wipeleft': 'wipeleft',
    'wiperight': 'wiperight',
    'wipeup': 'wipeup',
    'wipedown': 'wipedown',
    'radial': 'radial',
    'zoomblur': 'zoomin',
    'pagecurl': 'fade',
    'shutter': 'horzopen',
}


def apply_video_effect(input_path: str, effect_key: str, output_path: str | None = None) -> str:
    """对视频应用特效（颜色调整、模糊等），返回输出路径。"""
    filter_str = EFFECT_FILTERS.get(effect_key)
    if not filter_str:
        if output_path:
            import shutil
            shutil.copy2(input_path, output_path)
            return output_path
        return input_path

    input_path = Path(input_path)
    if output_path is None:
        output_path = str(input_path.parent / f"{input_path.stem}_fx{input_path.suffix}")

    cmd = [
        FFMPEG, "-y",
        "-i", str(input_path),
        "-vf", filter_str,
        "-c:a", "copy",
        str(output_path),
    ]
    _run(cmd, check=True, capture_output=True)
    return str(output_path)


def concat_with_xfade(
        segment_paths: list[str],
        transitions: list[dict],
        output_path: str,
        target_width: int | None = None,
        target_height: int | None = None,
) -> str:
    """使用 xfade 滤镜将多个视频片段按转场拼接。

    transitions: 长度 = len(segment_paths) - 1，每个元素为 {key, duration} 或 None（无转场）
    """
    import shutil

    n = len(segment_paths)
    if n == 0:
        raise ValueError("没有视频片段可供拼接")
    if n == 1:
        shutil.copy2(segment_paths[0], output_path)
        return output_path

    # Build xfade filter chain
    filter_parts = []
    prev_label = "0:v"

    # Probe each segment for duration
    durations = []
    for sp in segment_paths:
        try:
            probe = _run(
                [FFPROBE, "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(sp)],
                capture_output=True, text=True, timeout=10,
            )
            durations.append(float(probe.stdout.strip()) if probe.stdout.strip() else 3.0)
        except Exception:
            durations.append(3.0)

    # Scale filter if target dimensions are set
    scale_filter = ""
    if target_width and target_height:
        scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,"

    # Build input labels and chain
    for i in range(n):
        filter_parts.append(f"[{i}:v]{scale_filter}setpts=PTS-STARTPTS,fps=30[v{i}]")

    accum_dur = 0.0
    for i in range(n - 1):
        trans = transitions[i] if i < len(transitions) else None
        t_key = trans.get("key", "") if trans else ""
        t_dur = (trans.get("duration", 15) or 15) if trans else 15
        xfade_name = XFADE_MAP.get(t_key, "fade")
        dur_sec = max(0.1, t_dur / 30.0)  # frames to seconds

        # Offset: start of second segment minus transition duration
        accum_dur += durations[i]
        offset = max(0.0, accum_dur - dur_sec)

        next_label = f"x{i}"
        filter_parts.append(
            f"[{prev_label.replace(':', '')}][v{i + 1}]xfade=transition={xfade_name}:duration={dur_sec:.2f}:offset={offset:.2f}[{next_label}]"
        )
        prev_label = f"{next_label}"

    filter_graph = ";".join(filter_parts)

    # Build ffmpeg command
    cmd = [FFMPEG, "-y"]
    for sp in segment_paths:
        cmd.extend(["-i", str(sp)])
    cmd.extend(["-filter_complex", filter_graph])
    cmd.extend(["-map", f"[{prev_label}]"])
    # Try to include first segment's audio
    cmd.extend(["-map", "0:a?"])
    cmd.extend(["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p"])
    cmd.extend(["-c:a", "aac"])
    cmd.append(str(output_path))

    _run(cmd, check=True, capture_output=True)
    return str(output_path)
    return output_path
