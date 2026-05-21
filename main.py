"""Video-Capture 后端入口 — 启动 uvicorn 服务于 127.0.0.1:8090。"""
import io
import os
import sys
import traceback
from pathlib import Path


def _get_crash_log_path():
    """崩溃日志路径（%APPDATA%/Video Capture/logs/crash.log）。"""
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    log_dir = Path(appdata) / "Video Capture" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "crash.log"


# ── 强制 UTF-8 编码 ──
# Windows 中文版默认使用 GBK 编码的 stdout/stderr，无法输出 emoji 等 Unicode 字符。
# 开发模式：reconfigure 控制台流为 UTF-8（Python 3.7+）。
# 打包模式：重定向到 UTF-8 日志文件（--windowed 无控制台，或 pipe 模式）。
for _name in ("stdout", "stderr"):
    _stream = getattr(sys, _name)
    if _stream is None:
        continue
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    elif hasattr(_stream, "buffer"):
        # 旧版 Python 回退：用 TextIOWrapper 重新包装
        try:
            setattr(sys, _name,
                    io.TextIOWrapper(_stream.buffer, encoding="utf-8", errors="replace"))
        except Exception:
            pass

if getattr(sys, "frozen", False):
    try:
        _appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        _log_dir = Path(_appdata) / "Video Capture" / "logs"
        _log_dir.mkdir(parents=True, exist_ok=True)
        _log_path = _log_dir / "app.log"
        _log_fh = open(_log_path, "a", encoding="utf-8", buffering=1)
        _log_fh.write(f"\n{'=' * 60}\n")
        _log_fh.write(f"Video Capture Server 启动\n")
        _log_fh.write(f"{'=' * 60}\n")

        # 保留原始输出流（Electron 通过 pipe 捕获），同时写入日志文件便于事后排查
        _orig_out = sys.__stdout__
        _orig_err = sys.__stderr__

        class _TeeWriter:
            def __init__(self, *targets):
                self.targets = [t for t in targets if t is not None]

            def write(self, s):
                for t in self.targets:
                    try:
                        t.write(s)
                        t.flush()
                    except Exception:
                        pass

            def flush(self):
                for t in self.targets:
                    try:
                        t.flush()
                    except Exception:
                        pass

        sys.stdout = _TeeWriter(_orig_out, _log_fh)
        sys.stderr = _TeeWriter(_orig_err, _log_fh)
    except Exception:
        sys.exit(1)


# 用 try/except 包裹整个启动流程，确保任何未捕获异常都写入崩溃日志
try:
    import uvicorn

    # 设置 moviepy/imageio 使用的 ffmpeg 路径
    if getattr(sys, "frozen", False):
        _bin_dir = Path(sys.executable).parent / "bin"
    else:
        _bin_dir = Path(__file__).resolve().parent / "bin"

    _ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    _ffmpeg_path = _bin_dir / _ffmpeg_name
    if _ffmpeg_path.exists():
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", str(_ffmpeg_path))
        os.environ.setdefault("FFMPEG_BINARY", str(_ffmpeg_path))
        print(f"ffmpeg 路径: {_ffmpeg_path}")
    else:
        print(f"警告: ffmpeg 未找到 ({_ffmpeg_path})，依赖 ffmpeg 的功能可能不可用")

    # 启动阶段延迟导入到 crash logging 就绪之后
    from src.api.app import create_app

    print("正在创建 FastAPI 应用...")
    app = create_app()

    if __name__ == "__main__":
        import asyncio as _asyncio

        # 抑制 Windows ProactorEventLoop 在客户端断开时的 ConnectionResetError 噪声日志
        if sys.platform == "win32":

            def _patched_handler(loop, context):
                exc = context.get("exception")
                if exc is not None and isinstance(exc, (ConnectionResetError, ConnectionAbortedError)):
                    return
                loop.default_exception_handler(context)

            _Proactor = _asyncio.ProactorEventLoop
            _orig_init = _Proactor.__init__

            def _patched_init(self, *args, **kwargs):
                _orig_init(self, *args, **kwargs)
                self.set_exception_handler(_patched_handler)

            _Proactor.__init__ = _patched_init

        print("uvicorn 启动: http://127.0.0.1:8090")
        uvicorn.run(app, host="127.0.0.1", port=8090, access_log=False, log_config=None)

except Exception:
    # 崩溃日志写入 %APPDATA%/Video Capture/logs/crash.log
    try:
        crash_path = _get_crash_log_path()
        with open(crash_path, "a", encoding="utf-8") as f:
            f.write(f"\n[CRASH] 未捕获异常:\n")
            traceback.print_exc(file=f)
            f.write(f"\n")
    except Exception:
        traceback.print_exc()  # 最后的挣扎：如果连文件都写不了，至少试试 stderr
    sys.exit(1)
