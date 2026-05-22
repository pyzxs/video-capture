"""B站视频下载器"""

import asyncio
import os
import re
from pathlib import Path
from typing import Callable, Optional

import aiohttp
import yt_dlp

from .base import BaseDownloader, VideoInfo
from ..utils import get_ffmpeg_path

_ffmpeg_exe = get_ffmpeg_path()


class BilibiliDownloader(BaseDownloader):
    """B站视频下载器（基于 yt-dlp）"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
    }

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取B站视频信息"""
        bvid = self._extract_bvid(url)
        return await self._get_info_by_bvid(bvid)

    async def download_video(
        self,
        video_info: VideoInfo,
        show_progress: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Path:
        """使用 yt-dlp 下载B站视频"""
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
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(output_path.with_suffix('')) + '.%(ext)s',
            "merge_output_format": "mp4",
            "ffmpeg_location": _ffmpeg_exe,
            "quiet": not show_progress,
            "no_warnings": True,
            "extract_flat": False,
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

        # yt-dlp 会在 outtmpl 基础上追加扩展名，查找实际输出文件
        downloaded_file = self._find_downloaded_file(output_path.stem)
        if not downloaded_file:
            raise Exception("下载完成但未找到输出文件")

        if show_progress:
            print(f"✓ 视频已保存: {downloaded_file}")

        return downloaded_file

    @classmethod
    def match_url(cls, url: str) -> bool:
        """判断是否为B站链接"""
        patterns = [
            r"bilibili\.com",
            r"b23\.tv",
        ]
        return any(re.search(p, url) for p in patterns)

    def _extract_bvid(self, url: str) -> Optional[str]:
        """提取BV号"""
        match = re.search(r"BV\w+", url)
        if match:
            return match.group(0)

        match = re.search(r"av(\d+)", url, re.IGNORECASE)
        if match:
            return f"av{match.group(1)}"

        return None

    async def _get_info_by_bvid(self, bvid: str) -> VideoInfo:
        """通过BV号获取信息"""
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=self.HEADERS) as response:
                data = await response.json()

                if data.get("code") != 0:
                    raise Exception(f"获取视频信息失败: {data.get('message')}")

                video_data = data.get("data", {})

                video_url = f"https://www.bilibili.com/video/{bvid}"

                return VideoInfo(
                    video_id=bvid,
                    title=self._sanitize_filename(video_data.get("title", f"bilibili_{bvid}")),
                    url=video_url,
                    platform="bilibili",
                    author=video_data.get("owner", {}).get("name"),
                    duration=video_data.get("duration"),
                    description=video_data.get("desc", "")[:500],
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
