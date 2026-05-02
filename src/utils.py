"""纯工具函数：时间格式转换、SRT/ASS 字幕解析。"""
import mimetypes
import re
import struct
from datetime import datetime
from pathlib import Path

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
    """通过解析文件头获取图片宽高，返回 (width, height)。不依赖任何第三方库。"""
    path = Path(image_path)
    suffix = path.suffix.lower()

    with open(path, "rb") as f:
        header = f.read(30)

    if len(header) < 2:
        raise ValueError("文件太小，无法识别图片格式")

    # JPEG: 0xFF 0xD8
    if header[:2] == b"\xff\xd8":
        return _jpeg_size(path)

    # PNG: 89 50 4E 47
    if header[:4] == b"\x89PNG":
        if len(header) < 24:
            raise ValueError("PNG 头不完整")
        w, h = struct.unpack(">II", header[16:24])
        return w, h

    # GIF: GIF87a / GIF89a
    if header[:3] == b"GIF":
        w, h = struct.unpack("<HH", header[6:10])
        return w, h

    # BMP
    if header[:2] == b"BM":
        if len(header) < 26:
            raise ValueError("BMP 头不完整")
        w, h = struct.unpack("<ii", header[18:26])
        return w, abs(h)

    # WebP
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        webp_type = header[12:16]
        if webp_type == b"VP8 ":
            # VP8 lossy: frame tag(3) + start code(3), then width+height as 14-bit LE
            with open(path, "rb") as f:
                f.seek(26)
                raw = f.read(4)
            w, h = struct.unpack("<HH", raw)
            return w & 0x3FFF, h & 0x3FFF
        elif webp_type == b"VP8L":
            # VP8L lossless: width-1 (14bit), height-1 (14bit) packed in 4 bytes LE
            with open(path, "rb") as f:
                f.seek(21)
                raw = f.read(4)
            data = raw[0] | (raw[1] << 8) | (raw[2] << 16) | (raw[3] << 24)
            w = (data & 0x3FFF) + 1
            h = ((data >> 14) & 0x3FFF) + 1
            return w, h
        elif webp_type == b"VP8X":
            # VP8X extended: width+1, height+1 as 3 bytes LE each
            with open(path, "rb") as f:
                f.seek(24)
                raw = f.read(6)
            w = 1 + (raw[0] | raw[1] << 8 | raw[2] << 16)
            h = 1 + (raw[3] | raw[4] << 8 | raw[5] << 16)
            return w, h

    raise ValueError(f"不支持的图片格式: {suffix}")


def _jpeg_size(path: Path):
    """从 JPEG 文件中读取 SOF 段获取宽高。"""
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError("不是有效的 JPEG 文件")
        while True:
            marker_byte = f.read(1)
            if len(marker_byte) < 1:
                raise ValueError("JPEG 文件意外结束")
            # 跳过 0xFF 填充字节
            while marker_byte == b"\xff":
                marker_byte = f.read(1)
                if len(marker_byte) < 1:
                    raise ValueError("JPEG 文件意外结束")
            marker = marker_byte[0]
            # 跳过非 SOF 段
            if 0xC0 <= marker <= 0xC3 or 0xC5 <= marker <= 0xC7 or 0xC9 <= marker <= 0xCB or 0xCD <= marker <= 0xCF:
                f.read(3)  # 跳过段长度(2) + 精度(1)
                h, w = struct.unpack(">HH", f.read(4))
                return w, h
            elif marker == 0xD9:  # EOI
                raise ValueError("JPEG 文件中未找到 SOF 标记")
            else:
                seg_len = struct.unpack(">H", f.read(2))[0]
                f.seek(f.tell() + seg_len - 2)


def generate_thumbnail(video_path: str) -> str:
    """从视频第1秒提取一帧作为缩略图，返回缩略图文件路径。失败返回空字符串。"""
    import hashlib
    import subprocess
    from src.config import BASE_DIR, get_config

    thumb_dir = get_config("thumbnail_dir")
    thumb_dir.mkdir(parents=True, exist_ok=True)
    file_hash = hashlib.md5(video_path.encode()).hexdigest()
    thumb_path = thumb_dir / f"{file_hash}.jpg"
    if thumb_path.exists():
        return str(thumb_path)
    try:
        subprocess.run([
            f"{BASE_DIR}/bin/ffmpeg", "-ss", "5", "-i", video_path,
            "-frames:v", "1", "-q:v", "3", "-vf", "scale=320:-1",
            str(thumb_path), "-y",
        ], check=True, capture_output=True, timeout=10)
        return str(thumb_path)
    except Exception:
        return ""


def thumb_url(filepath: str) -> str:
    """将缩略图文件路径转为前端可用的 URL。"""
    if not filepath:
        return ""
    return f"/api/thumbnails/{Path(filepath).name}"
