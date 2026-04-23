"""硅基流动 TTS API 封装（FunAudioLLM/CosyVoice2-0.5B），提供语音合成与配音功能。"""

import subprocess
from pathlib import Path

import os

import requests

from src.config import OUTPUT_DIR, SILICONFLOW_API_KEY, TTS_MODEL, TTS_VOICE

_TTS_BASE_URL = (os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
                 + "/audio/speech")


def synthesize(text: str, output_path: str | None = None,
               voice: str | None = None) -> str:
    """使用硅基流动 API 将文本合成为语音文件。

    参数：
        text: 要合成的文本。
        output_path: 输出音频路径（为 None 时自动生成）。
        voice: 音色标识，如 "FunAudioLLM/CosyVoice2-0.5B:anna"。

    返回输出音频文件路径。
    """
    if not SILICONFLOW_API_KEY:
        raise RuntimeError("未配置 SILICONFLOW_API_KEY")

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(OUTPUT_DIR / "tts_output.mp3")

    voice = voice or TTS_VOICE

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": TTS_MODEL,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }

    resp = requests.post(_TTS_BASE_URL, json=payload, headers=headers, stream=True)
    if resp.status_code != 200:
        raise RuntimeError(
            f"TTS API 请求失败 (HTTP {resp.status_code}): {resp.text[:500]}"
        )

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

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
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(OUTPUT_DIR / f"{video_path.stem}_dubbed{video_path.suffix}")

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


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
    print("[1/2] 正在合成语音...")
    audio_path = synthesize(text, voice=voice)
    print(f"  → {audio_path}")

    print("[2/2] 正在替换视频音轨...")
    result = dub_video(video_path, audio_path, output_path)
    print(f"  → {result}")

    print("✓ 配音完成。")
    return result
