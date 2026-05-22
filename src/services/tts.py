"""TTS 语音合成与视频配音。"""
import hashlib
import re
import subprocess
from pathlib import Path

from src.config import get_config
from src.utils import ensure_date_dir, get_ffmpeg_path, _CREATIONFLAGS
from src.logger import default_logger as logger

ffmpeg_bin = get_ffmpeg_path()

_SPLIT_RE = re.compile(r"(?<=[。！？\n])")
_CHUNK_MAX = 500


def _split_text_chunks(text: str) -> list[str]:
    """将文本按句子拆分，再合并为不超过 _CHUNK_MAX 字的块。"""
    parts = _SPLIT_RE.split(text)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return [text]

    chunks = []
    buf = ""
    for p in parts:
        if buf and len(buf) + len(p) > _CHUNK_MAX:
            chunks.append(buf)
            buf = p
        else:
            buf += p
    if buf:
        chunks.append(buf)
    return chunks


def _synthesize_chunk(text: str, voice: str, cms_url: str, headers: dict,
                      model: str) -> bytes:
    """合成单个文本块，返回音频字节。"""
    from src.http_client import sync_post

    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }
    resp = sync_post(f"{cms_url}/api/proxy/tts", json=payload, headers=headers, timeout=120)
    if resp.status_code == 402:
        raise RuntimeError("CMS 额度不足，请充值")
    if resp.status_code >= 400:
        raise RuntimeError(f"TTS 代理请求失败 (HTTP {resp.status_code}): {resp.text[:200]}")
    return resp.content


def synthesize(text: str, output_path: str | None = None,
               voice: str | None = None) -> str:
    """通过 CMS 代理调用 TTS 将文本合成为语音文件。

    优化策略：
    1. 缓存：相同文本直接返回已有文件
    2. 分段并行：长文本拆分为多个块并发合成，再拼接

    返回输出音频文件路径。
    """
    from src.auth import get_auth_headers, update_local_quota

    if not get_config("api_key"):
        raise RuntimeError("未注册 CMS 用户，无法使用 TTS")

    if output_path is None:
        filename = hashlib.md5(text.encode('utf-8')).hexdigest()
        output_path = str(ensure_date_dir(get_config("mixed_dir"), f"{filename}.mp3"))

    # 缓存命中
    if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
        return output_path

    voice = voice or get_config("tts_voice")
    cms_url = get_config("cms_base_url")
    model = get_config("tts_model")
    headers = {"Content-Type": "application/json", **get_auth_headers()}

    chunks = _split_text_chunks(text)

    if len(chunks) <= 1:
        # 短文本：单次请求
        audio_data = _synthesize_chunk(text, voice, cms_url, headers, model)
        remaining = None  # single chunk, quota handled below
        with open(output_path, "wb") as f:
            f.write(audio_data)
        return output_path

    # 长文本：并行合成多个块
    from concurrent.futures import ThreadPoolExecutor, as_completed

    max_workers = min(len(chunks), 5)
    chunk_results = [None] * len(chunks)
    tmp_dir = Path(output_path).parent

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_synthesize_chunk, chunk, voice, cms_url, headers, model): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            chunk_results[idx] = future.result()

    # 写入临时文件并用 ffmpeg concat 拼接
    tmp_files = []
    try:
        for i, data in enumerate(chunk_results):
            tmp_path = tmp_dir / f"_tts_chunk_{i}.mp3"
            with open(tmp_path, "wb") as f:
                f.write(data)
            tmp_files.append(tmp_path)

        list_file = tmp_dir / "_tts_concat_list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for tp in tmp_files:
                f.write(f"file '{tp}'\n")

        cmd = [
            ffmpeg_bin,
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-y", output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, creationflags=_CREATIONFLAGS)
    finally:
        for tp in tmp_files:
            tp.unlink(missing_ok=True)
        list_path = tmp_dir / "_tts_concat_list.txt"
        list_path.unlink(missing_ok=True)

    return output_path


def dub_video(video_path: str, audio_path: str, output_path: str | None = None) -> str:
    """用生成的音频替换视频的音轨。

    参数：
        video_path: 源视频路径。
        audio_path: 配音音频路径。
        output_path: 输出视频路径（为 None 时自动生成）。

    返回输出视频路径。
    """
    video_path = Path(video_path)
    if output_path is None:
        output_path = str(ensure_date_dir(get_config("mixed_dir"), f"{video_path.stem}_dubbed{video_path.suffix}"))

    output_path = Path(output_path)
    # 使用临时文件避免输入/输出路径相同导致 ffmpeg 失败
    tmp = output_path.with_suffix(".tmp.mp4")
    cmd = [
        ffmpeg_bin, "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-y", str(tmp),
    ]
    subprocess.run(cmd, creationflags=_CREATIONFLAGS, check=True, capture_output=True)
    if output_path.exists():
        output_path.unlink()
    tmp.rename(output_path)
    return str(output_path)


def dub_from_text(video_path: str, text: str, voice: str | None = None,
                  output_path: str | None = None) -> str:
    """一键配音：文本 → 语音合成 → 替换视频音轨。

    参数：
        video_path: 源视频路径。
        text: 配音文本。
        voice: 音色标识，为 None 时使用配置默认值。
        output_path: 输出视频路径（为 None 时自动生成）。

    返回输出视频路径。
    """
    logger.info("[1/2] 正在合成语音...")
    audio_path = synthesize(text, voice=voice)
    logger.info("  → %s", audio_path)

    logger.info("[2/2] 正在替换视频音轨...")
    result = dub_video(video_path, audio_path, output_path)
    logger.info("  → %s", result)

    logger.info("✓ 配音完成。")
    return result
