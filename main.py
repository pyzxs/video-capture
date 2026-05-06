"""Video-Capture CLI — 委托给 src.cli。"""
import os
import sys
from pathlib import Path

import uvicorn

# --windowed 模式下 sys.stdout/sys.stderr 为 None，uvicorn 日志初始化会崩溃
if sys.stdout is None:
    log_dir = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / 'Video Capture' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = (log_dir / 'app.log').open('a', encoding='utf-8')
    sys.stdout = log_file
    sys.stderr = log_file

from src.api.app import create_app

app = create_app()

if __name__ == "__main__":
    # 抑制 Windows ProactorEventLoop 在客户端断开时的 ConnectionResetError 噪声日志
    if sys.platform == "win32":
        import asyncio as _asyncio
        _loop = _asyncio.get_event_loop()
        def _patched_handler(loop, context):
            exc = context.get("exception")
            if exc is not None and isinstance(exc, (ConnectionResetError, ConnectionAbortedError)):
                return
            loop.default_exception_handler(context)
        _loop.set_exception_handler(_patched_handler)

    uvicorn.run(app, host="127.0.0.1", port=8090)
