"""TTS 语音合成与视频配音。"""
import hashlib
import subprocess
import sys
from pathlib import Path

from src.config import get_config, BASE_DIR
from src.utils import ensure_date_dir
from src.logger import default_logger as logger

_CREATIONFLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

ffmpeg_bin = str(Path(BASE_DIR) / "bin" / "ffmpeg")


def synthesize(text: str, output_path: str | None = None,
               voice: str | None = None) -> str:
    """通过 CMS 代理调用 TTS 将文本合成为语音文件。

    参数：
        text: 要合成的文本。
        output_path: 输出音频路径（为 None 时自动生成）。
        voice: 音色标识，如 "FunAudioLLM/CosyVoice2-0.5B:anna"。

    返回输出音频文件路径。
    """
    from src.auth import get_auth_headers, update_local_quota
    from src.http_client import sync_post

    if not get_config("api_key"):
        raise RuntimeError("未注册 CMS 用户，无法使用 TTS")

    if output_path is None:
        filename = hashlib.md5(text.encode('utf-8')).hexdigest()
        output_path = str(ensure_date_dir(get_config("mixed_dir"), f"{filename}.mp3"))

    voice = voice or get_config("tts_voice")
    cms_url = get_config("cms_base_url")

    headers = {"Content-Type": "application/json", **get_auth_headers()}
    payload = {
        "model": get_config("tts_model"),
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }

    resp = sync_post(
        f"{cms_url}/api/proxy/tts",
        json=payload, headers=headers, timeout=60,
    )
    if resp.status_code == 402:
        raise RuntimeError("CMS 额度不足，请充值")
    if resp.status_code >= 400:
        raise RuntimeError(
            f"TTS 代理请求失败 (HTTP {resp.status_code}): {resp.text[:500]}"
        )

    remaining = resp.headers.get("X-Quota-Remaining")
    if remaining:
        update_local_quota(float(remaining))

    with open(output_path, "wb") as f:
        f.write(resp.content)

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
    subprocess.run(creationflags=_CREATIONFLAGS,cmd, check=True, capture_output=True)
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
