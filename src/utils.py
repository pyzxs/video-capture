"""纯工具函数：时间格式转换、SRT/ASS 字幕解析。"""
import mimetypes
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import imageio.v3 as iio
from src.config import API_BASE_URL, BASE_DIR

_CREATIONFLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# ffmpeg/ffprobe 路径：
#   Windows：打包时捆绑在 backend/bin/ 下，开发时在项目 bin/ 下
#   macOS/Linux：使用系统 PATH 中的 ffmpeg（用户自行安装）
if sys.platform == "win32":
    if getattr(sys, 'frozen', False):
        _bin_dir = Path(sys.executable).parent / "bin"
    else:
        _bin_dir = Path(BASE_DIR) / "bin"
    _ffmpeg_bin = str(_bin_dir / "ffmpeg.exe")
    _ffprobe_bin = str(_bin_dir / "ffprobe.exe")
else:
    _ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    _ffprobe_bin = shutil.which("ffprobe") or "ffprobe"


def get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径。"""
    return _ffmpeg_bin


def get_ffprobe_path() -> str:
    """获取 ffprobe 可执行文件路径。"""
    return _ffprobe_bin

_TIMESTAMP_RE = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d+)"
)


def ts_to_seconds(ts: str) -> float:
    """将 SRT/ASS 时间戳转换为秒数。

    支持格式：
      - SRT:  00:00:01,000  (时=2位, 毫秒=3位)
      - ASS:  0:00:01.00    (时=1位, 厘秒=2位)
    """
    m = _TIMESTAMP_RE.match(ts)
    if not m:
        return 0.0
    h, mi, s, ms_part = int(m[1]), int(m[2]), int(m[3]), m[4]
    # ASS 厘秒（2位）→ 毫秒（3位），SRT 已是毫秒
    if len(ms_part) == 2:
        ms = int(ms_part) * 10
    else:
        ms = int(ms_part)
    return h * 3600 + mi * 60 + s + ms / 1000


def format_time(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳（HH:MM:SS,mmm）。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = round((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def date_storage_path(base_dir: str | Path, filename: str) -> Path:
    """生成按年月日分目录的存储路径：<base_dir>/YYYY/MM/DD/<filename>"""
    now = datetime.now()
    return Path(base_dir) / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}" / filename


def ensure_date_dir(base_dir: str | Path, filename: str) -> Path:
    """生成日期分目录路径并确保目录存在。"""
    path = date_storage_path(base_dir, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_filename_mime(filename: Path) -> str:
    """获取文件mime信息"""
    mime_type, _ = mimetypes.guess_type(str(filename))
    if not mime_type:
        ext = filename.suffix.lower()
        mime_map = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.flac': 'audio/flac',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg'
        }
        mime_type = mime_map.get(ext, 'application/octet-stream')
    return mime_type


def get_image_size(image_path):
    """使用 imageio 获取图片宽高，返回 (width, height)。"""
    props = iio.improps(image_path)
    h, w = props.shape[0], props.shape[1]
    return w, h


def generate_thumbnail(video_path: str) -> str:
    """从视频第1秒提取一帧作为缩略图，返回缩略图文件路径。失败返回空字符串。"""
    import hashlib
    from src.config import API_BASE_URL, BASE_DIR, get_config

    thumb_dir = get_config("thumbnail_dir")
    thumb_dir.mkdir(parents=True, exist_ok=True)
    file_hash = hashlib.md5(video_path.encode()).hexdigest()
    thumb_path = thumb_dir / f"{file_hash}.jpg"
    if thumb_path.exists():
        return str(thumb_path)
    try:
        subprocess.run([
            _ffmpeg_bin, "-ss", "5", "-i", video_path,
            "-frames:v", "1", "-q:v", "3", "-vf", "scale=320:-1",
            str(thumb_path), "-y",
        ], check=True, capture_output=True, timeout=10, creationflags=_CREATIONFLAGS)
        return str(thumb_path)
    except Exception:
        return ""


def thumb_url(filepath: str) -> str:
    """将缩略图文件路径转为前端可用的 URL。

    使用绝对 URL（而非相对路径），避免 Electron 打包后 file:// 协议
    下 <img src> 将相对路径解析为 file:///api/... 导致缩略图无法加载。
    """
    if not filepath:
        return ""
    return f"{API_BASE_URL}/api/thumbnails/{Path(filepath).name}"
