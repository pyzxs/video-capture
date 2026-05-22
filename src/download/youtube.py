"""YouTube视频下载器（使用yt-dlp）"""

import asyncio
import re
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from .base import BaseDownloader, VideoInfo
from ..utils import get_ffmpeg_path

_ffmpeg_exe = get_ffmpeg_path()


class YouTubeDownloader(BaseDownloader):
    """YouTube视频下载器（基于yt-dlp）"""

    def __init__(self, output_dir: Path = Path("./output")):
        super().__init__(output_dir)

        self.proxy = None

        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        cookies_file = Path(__file__).resolve().parent.parent.parent / "resource" / "cookies.txt"
        if cookies_file.exists():
            self.ydl_opts["cookiefile"] = str(cookies_file)
            print(f"[YouTube] 使用cookies文件: {cookies_file}")

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取YouTube视频信息"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: _extract_info(self.ydl_opts, url),
        )

    async def download_video(
        self,
        video_info: VideoInfo,
        show_progress: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Path:
        """下载YouTube视频"""
        existing_file = self._check_file_exists(video_info)
        if existing_file:
            if show_progress:
                print(f"✓ 视频已存在，跳过下载: {existing_file}")
            if progress_callback:
                progress_callback(100)
            return existing_file

        self.output_dir.mkdir(parents=True, exist_ok=True)

        output_path = self._get_video_filepath(video_info)

        ydl_opts = {
            **self.ydl_opts,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(output_path.with_suffix('')) + '.%(ext)s',
            "merge_output_format": "mp4",
            "ffmpeg_location": _ffmpeg_exe,
            "quiet": not show_progress,
            "format_sort": ["res", "codec:h264"],
            "postprocessors": [{
                "key": "SponsorBlock",
                "categories": ["sponsor"],
                "when": "after_filter",
            }],
        }

        if show_progress:
            print(f"正在使用 yt-dlp 下载: {video_info.title}")

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: _do_download(ydl_opts, video_info.url, progress_callback),
            )
        except Exception as e:
            raise Exception(f"yt-dlp 下载失败: {str(e)[:500]}") from e

        downloaded_file = self._find_downloaded_file(output_path.stem)
        if not downloaded_file:
            raise Exception("下载完成但未找到输出文件")

        if show_progress:
            print(f"✓ 视频已保存: {downloaded_file}")

        return downloaded_file

    @classmethod
    def match_url(cls, url: str) -> bool:
        """判断是否为YouTube链接"""
        patterns = [
            r"youtube\.com",
            r"youtu\.be",
        ]
        return any(re.search(p, url) for p in patterns)


def _extract_info(ydl_opts: dict, url: str) -> VideoInfo:
    """通过 yt-dlp 提取视频信息"""
    ydl_opts = ydl_opts.copy()

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        video_url = None
        for fmt in info.get("formats", []):
            if fmt.get("ext") == "mp4" and fmt.get("vcodec") != "none":
                video_url = fmt.get("url")
                break

        title = info.get("title") or ""
        title = re.sub(r'[\\/:*?"<>|]', "_", title)[:200]

        return VideoInfo(
            video_id=info.get("id", ""),
            title=title,
            url=video_url or url,
            platform="youtube",
            author=info.get("uploader"),
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            description=str(info.get("description") or "")[:500],
            metadata=info,
        )


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
