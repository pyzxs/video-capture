from pathlib import Path

from src.processing.asr import get_asr_model


def test_one():
    model = get_asr_model()
    audio_path = r"D:\workspace\video-project\video-capture\storage\output\video-project-asr\asr_11_0.0_10.0.wav"
    result = model.transcribe(audio_path)
    print(result)

def test_env():
    import os
    from faster_whisper import WhisperModel

    ffmpeg_bin_dir = Path(r'D:\workspace/video-project/video-capture/bin').resolve()
    os.environ['PATH'] = f'{ffmpeg_bin_dir}{os.pathsep}{os.environ["PATH"]}'

    print(os.environ["PATH"])
    if not any(
            os.path.exists(os.path.join(ffmpeg_bin_dir, f'ffmpeg{ext}'))
            for ext in ['', '.exe']
    ):
        print(f"警告：在 {ffmpeg_bin_dir} 中未找到 FFmpeg 可执行文件。")

    model = WhisperModel("base", device="cpu", compute_type="int8")
    audio_path = r"D:\workspace\video-project\video-capture\storage\output\video-project-asr\asr_11_0.0_10.0.wav"
    segments, info = model.transcribe(audio_path)
    for seg in segments:
        print(seg.text)