"""YouTube视频下载器（使用yt-dlp）"""

import os
import re
from pathlib import Path

import yt_dlp

from .base import BaseDownloader, VideoInfo


class YouTubeDownloader(BaseDownloader):
    """YouTube视频下载器（基于yt-dlp）"""

    def __init__(self, output_dir: Path = Path("./output")):
        super().__init__(output_dir)

        # 从环境变量获取代理设置
        self.proxy = (
            os.getenv("YOUTUBE_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
        )

        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        # 如果设置了代理，添加到选项
        if self.proxy:
            self.ydl_opts["proxy"] = self.proxy

        # 固定读取 resource/cookies.txt
        cookies_file = Path(__file__).resolve().parent.parent.parent / "resource" / "cookies.txt"
        if cookies_file.exists():
            self.ydl_opts["cookiefile"] = str(cookies_file)
            print(f"[YouTube] 使用cookies文件: {cookies_file}")

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取YouTube视频信息"""
        ydl_opts = self.ydl_opts.copy()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)

                # 获取最佳视频URL
                video_url = None
                for format in info.get("formats", []):
                    if format.get("ext") == "mp4" and format.get("vcodec") != "none":
                        video_url = format.get("url")
                        break

                return VideoInfo(
                    video_id=info.get("id", ""),
                    title=self._sanitize_filename(info.get("title", "")),
                    url=video_url or url,
                    platform="youtube",
                    author=info.get("uploader"),
                    duration=info.get("duration"),
                    thumbnail=info.get("thumbnail"),
                    description=info.get("description", "")[:500],
                    metadata=info,
                )
            except Exception as e:
                raise Exception(f"获取YouTube视频信息失败: {e}")

    async def download_video(self, video_info: VideoInfo, show_progress: bool = True) -> Path:
        """下载YouTube视频"""
        # 检查文件是否已存在
        existing_file = self._check_file_exists(video_info)
        if existing_file:
            if show_progress:
                print(f"✓ 视频已存在，跳过下载: {existing_file}")
            return existing_file

        output_path = self._get_video_filepath(video_info)

        ydl_opts = {
            **self.ydl_opts,
            "format": "bestvideo*+bestaudio/best",
            "outtmpl": str(output_path),
            "quiet": not show_progress,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_info.url])

        if show_progress:
            print(f"✓ 视频已保存: {output_path}")

        return output_path

    @classmethod
    def match_url(cls, url: str) -> bool:
        """判断是否为YouTube链接"""
        patterns = [
            r"youtube\.com",
            r"youtu\.be",
        ]
        return any(re.search(p, url) for p in patterns)
