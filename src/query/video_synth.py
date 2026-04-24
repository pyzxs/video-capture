import os
import subprocess
from pathlib import Path

from src.config import OUTPUT_DIR


def composite_subtitles(video_path: str, srt_path: str, output_path: str | None = None) -> str:
    """使用 ffmpeg 将字幕压制到视频中。"""
    video_path = Path(video_path)
    if output_path is None:
        from src.config import OUTPUT_DIR
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(OUTPUT_DIR / f"{video_path.stem}_subtitled{video_path.suffix}")

    srt_filter_path = str(Path(srt_path).as_posix())

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"subtitles={srt_filter_path}:force_style='FontName=Noto Sans SC,FontSize=18,Alignment=2'",
        "-c:a", "copy",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def concat_videos(clip_paths: list[str], output_path: str) -> str:
    """将多个视频片段直接拼接（无转场），使用 concat demuxer 流复制。

    所有片段需具有相同的编解码参数，否则 ffmpeg 会报错。
    """
    print(f"{clip_paths}")
    n = len(clip_paths)
    if n == 0:
        raise ValueError("No clips to concatenate")

    output = Path(output_path).resolve()
    print(f"f 文件路径地址:{output}")
    if not output.suffix:
        raise ValueError(f"输出路径缺少文件扩展名: {output_path}")

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

    # 创建临时文件列表（绝对路径）
    list_path = output.parent / f"_concat_{os.getpid()}.txt"
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for p in clip_paths:
                f.write(f"file '{Path(p).resolve().as_posix()}'\n")

        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            "-y", str(output),
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
