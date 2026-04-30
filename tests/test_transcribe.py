from pathlib import Path

from src.processing.asr import get_asr_model


def test_one():
    model = get_asr_model()
    audio_path = r"D:\workspace\video-project\video-capture\storage\output\video-project-asr\asr_11_0.0_10.0.wav"
    result = model.transcribe(audio_path)
    print(result)

def test_env():
    import os
    import whisper

    # 将 'your_ffmpeg_bin_path' 替换为你的实际路径
    # 例如 Windows: r'D:\ffmpeg\bin'
    # 例如 macOS/Linux: '/usr/local/bin'
    ffmpeg_bin_dir = Path(r'D:\workspace/video-project/video-capture/bin').resolve()

    # 将路径添加到当前进程的环境变量中
    os.environ['PATH'] = f'{ffmpeg_bin_dir}{os.pathsep}{os.environ["PATH"]}'

    print(os.environ["PATH"])
    # 验证
    if not any(
            os.path.exists(os.path.join(ffmpeg_bin_dir, f'ffmpeg{ext}'))
            for ext in ['', '.exe']
    ):
        print(f"警告：在 {ffmpeg_bin_dir} 中未找到 FFmpeg 可执行文件。")

    # 正常使用 Whisper
    model = whisper.load_model("base")
    audio_path = r"D:\workspace\video-project\video-capture\storage\output\video-project-asr\asr_11_0.0_10.0.wav"
    result = model.transcribe(audio_path)
    print(result["text"])