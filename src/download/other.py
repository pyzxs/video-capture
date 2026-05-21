"""通用视频下载器（基于 yt-dlp）"""

import asyncio
import re
import sys
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from .base import BaseDownloader, VideoInfo
from ..config import BASE_DIR


# ffmpeg 路径
if getattr(sys, 'frozen', False):
    _bin_dir = Path(sys.executable).parent / "bin"
else:
    _bin_dir = Path(BASE_DIR) / "bin"

_ffmpeg_exe = str(_bin_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))


class OtherDownloader(BaseDownloader):
    """通用视频下载器（基于 yt-dlp）"""

    def __init__(self, output_dir: Path = Path("./output")):
        super().__init__(output_dir)

        self.proxy = None

        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取视频信息"""
        ydl_opts = self.ydl_opts.copy()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)

                video_url = None
                for fmt in info.get("formats", []):
                    if fmt.get("ext") == "mp4" and fmt.get("vcodec") != "none":
                        video_url = fmt.get("url")
                        break

                return VideoInfo(
                    video_id=info.get("id", self._extract_video_id(url)),
                    title=self._sanitize_filename(info.get("title", self._extract_domain(url))),
                    url=video_url or url,
                    platform=self._extract_platform(url),
                    author=info.get("uploader") or info.get("channel") or info.get("creator"),
                    duration=info.get("duration"),
                    thumbnail=info.get("thumbnail"),
                    description=str(info.get("description") or "")[:500],
                    metadata=info,
                )
            except Exception as e:
                raise Exception(f"yt-dlp获取视频信息失败: {e}")

    async def download_video(
        self,
        video_info: VideoInfo,
        show_progress: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Path:
        """下载视频"""
        existing_file = self._check_file_exists(video_info)
        if existing_file:
            if show_progress:
                print(f"✓ 视频已存在，跳过下载: {existing_file}")
            if progress_callback:
                progress_callback(100)
            return existing_file

        output_path = self._get_video_filepath(video_info)

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(output_path.with_suffix('')) + '.%(ext)s',
            "merge_output_format": "mp4",
            "ffmpeg_location": _ffmpeg_exe,
            "quiet": not show_progress,
            "no_warnings": True,
        }

        if self.proxy:
            ydl_opts["proxy"] = self.proxy
            if show_progress:
                print(f"[INFO] 使用代理: {self.proxy}")

        if show_progress:
            print(f"正在下载: {video_info.title}")

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: _do_download(ydl_opts, video_info.url, progress_callback),
            )
        except Exception as e:
            raise Exception(f"yt-dlp 下载失败: {str(e)[:500]}") from e

        # yt-dlp 会在 outtmpl 基础上追加扩展名，查找实际输出文件
        downloaded_file = self._find_downloaded_file(output_path.stem)
        if not downloaded_file:
            raise Exception("下载完成但未找到输出文件")

        if show_progress:
            print(f"✓ 视频已保存: {downloaded_file}")

        return downloaded_file

    def _extract_video_id(self, url: str) -> str:
        """从URL中提取视频ID"""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _extract_domain(self, url: str) -> str:
        """从URL中提取域名"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _extract_platform(self, url: str) -> str:
        """从URL中提取平台名称"""
        domain = self._extract_domain(url)
        platform_map = {
            "twitter.com": "twitter",
            "x.com": "twitter",
            "instagram.com": "instagram",
            "tiktok.com": "tiktok",
            "twitch.tv": "twitch",
            "vimeo.com": "vimeo",
            "dailymotion.com": "dailymotion",
            "facebook.com": "facebook",
            "nicovideo.jp": "niconico",
            "bilibili.com": "bilibili",
            "youtube.com": "youtube",
            "youtu.be": "youtube",
        }
        for key, value in platform_map.items():
            if key in domain:
                return value
        return domain.split(".")[0] if "." in domain else domain

    @classmethod
    def match_url(cls, url: str) -> bool:
        """判断是否为其他视频链接（排除已支持的平台）"""
        excluded_patterns = [
            r"douyin\.com", r"iesdouyin\.com",
            r"kuaishou\.com",
            r"xiaohongshu\.com", r"xhslink\.com",
            r"bilibili\.com", r"b23\.tv",
            r"youtube\.com", r"youtu\.be",
        ]

        for pattern in excluded_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False

        video_patterns = [
            r"\.mp4$", r"\.m3u8$", r"\.flv$", r"\.avi$", r"\.mov$",
            r"\.wmv$", r"\.webm$", r"video/", r"watch\?v=", r"/v/",
            r"vimeo\.com", r"twitter\.com", r"x\.com",
            r"instagram\.com", r"tiktok\.com", r"twitch\.tv",
            r"dailymotion\.com", r"facebook\.com", r"nicovideo\.jp",
            r"t\.co/", r"streamable\.com", r"gfycat\.com",
            r"reddit\.com.*/comments/.*/", r"imgur\.com", r"giphy\.com",
            r"tenor\.com", r"likee\.com", r"kwai\.com", r"snapchat\.com",
            r"pinterest\.com.*/pin/",
        ]

        for pattern in video_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        return True


def _do_download(ydl_opts: dict, url: str, progress_callback: Optional[Callable[[int], None]] = None) -> None:
    """同步执行 yt-dlp 下载"""
    if progress_callback:
        def _hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    progress_callback(min(99, int(downloaded * 100 / total)))
            elif d.get("status") == "finished":
                progress_callback(100)
        ydl_opts = {**ydl_opts, "progress_hooks": [_hook]}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
