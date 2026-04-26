"""通用视频下载器（使用yt-dlp和you-get）"""

import asyncio
import os
import re
from pathlib import Path

import yt_dlp

from .base import BaseDownloader, VideoInfo


class OtherDownloader(BaseDownloader):
    """通用视频下载器（基于yt-dlp和you-get）"""

    def __init__(self, output_dir: Path = Path("./output")):
        super().__init__(output_dir)

        # 从环境变量获取代理设置
        self.proxy = os.getenv("OTHER_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")

        # yt-dlp配置
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        # 如果设置了代理，添加到选项
        if self.proxy:
            self.ydl_opts["proxy"] = self.proxy

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取视频信息（优先使用yt-dlp）"""
        # 先尝试yt-dlp
        try:
            return await self._get_video_info_ytdlp(url)
        except Exception as e1:
            print(f"[INFO] yt-dlp获取信息失败: {e1}")

            # 如果yt-dlp失败，尝试you-get
            try:
                return await self._get_video_info_youget(url)
            except Exception as e2:
                print(f"[INFO] you-get获取信息失败: {e2}")
                raise Exception(f"获取视频信息失败: yt-dlp错误: {e1}, you-get错误: {e2}")

    async def _get_video_info_ytdlp(self, url: str) -> VideoInfo:
        """使用yt-dlp获取视频信息"""
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
                    video_id=info.get("id", self._extract_video_id(url)),
                    title=self._sanitize_filename(info.get("title", self._extract_domain(url))),
                    url=video_url or url,
                    platform=self._extract_platform(url),
                    author=info.get("uploader") or info.get("channel") or info.get("creator"),
                    duration=info.get("duration"),
                    thumbnail=info.get("thumbnail"),
                    description=info.get("description", "")[:500],
                    metadata=info,
                )
            except Exception as e:
                raise Exception(f"yt-dlp获取视频信息失败: {e}")

    async def _get_video_info_youget(self, url: str) -> VideoInfo:
        """使用you-get获取视频信息"""
        try:
            # 运行you-get获取信息
            cmd = ["you-get", "--json", url]

            # 添加代理
            if self.proxy:
                cmd.extend(["--http-proxy", self.proxy])

            result = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="ignore")
                raise Exception(f"you-get命令执行失败: {error_msg}")

            # 解析JSON输出
            import json

            info = json.loads(stdout.decode("utf-8", errors="ignore"))

            return VideoInfo(
                video_id=self._extract_video_id(url),
                title=self._sanitize_filename(info.get("title", self._extract_domain(url))),
                url=url,  # you-get不直接提供视频URL
                platform=self._extract_platform(url),
                author=info.get("uploader") or info.get("author"),
                duration=None,  # you-get可能不提供时长
                thumbnail=info.get("thumbnail"),
                description=info.get("description", "")[:500],
                metadata=info,
            )

        except Exception as e:
            raise Exception(f"you-get获取视频信息失败: {e}")

    async def download_video(self, video_info: VideoInfo, show_progress: bool = True) -> Path:
        """下载视频（先尝试yt-dlp，失败后尝试you-get）"""
        # 先尝试yt-dlp
        try:
            return await self._download_with_ytdlp(video_info, show_progress)
        except Exception as e1:
            print(f"[INFO] yt-dlp下载失败: {e1}")

            # 如果yt-dlp失败，尝试you-get
            try:
                return await self._download_with_youget(video_info, show_progress)
            except Exception as e2:
                print(f"[INFO] you-get下载失败: {e2}")
                raise Exception(f"下载视频失败: yt-dlp错误: {e1}, you-get错误: {e2}")

    async def _download_with_ytdlp(self, video_info: VideoInfo, show_progress: bool = True) -> Path:
        """使用yt-dlp下载视频"""
        # 检查文件是否已存在
        existing_file = self._check_file_exists(video_info)
        if existing_file:
            if show_progress:
                print(f"✓ 视频已存在，跳过下载: {existing_file}")
            return existing_file

        output_path = self._get_video_filepath(video_info)

        ydl_opts = {
            "format": "best[ext=mp4]",
            "outtmpl": str(output_path),
            "quiet": not show_progress,
            "no_warnings": True,
        }

        # 添加代理设置
        if self.proxy:
            ydl_opts["proxy"] = self.proxy
            if show_progress:
                print(f"[INFO] 使用代理: {self.proxy}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_info.url])

        if show_progress:
            print(f"✓ 视频已保存: {output_path}")

        return output_path

    async def _download_with_youget(
        self, video_info: VideoInfo, show_progress: bool = True
    ) -> Path:
        """使用you-get下载视频"""
        # 检查文件是否已存在
        existing_file = self._check_file_exists(video_info)
        if existing_file:
            if show_progress:
                print(f"✓ 视频已存在，跳过下载: {existing_file}")
            return existing_file

        output_path = self._get_video_filepath(video_info)

        cmd = [
            "you-get",
            "-o",
            str(self.output_dir),
            "-O",
            f"{video_info.platform}_{video_info.video_id}",
            video_info.url,
        ]

        # 添加代理
        if self.proxy:
            cmd.extend(["--http-proxy", self.proxy])
            if show_progress:
                print(f"[INFO] 使用代理: {self.proxy}")

        if show_progress:
            print(f"[INFO] 使用you-get下载: {video_info.url}")

        result = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="ignore")
            raise Exception(f"you-get下载失败: {error_msg}")

        if show_progress:
            print(f"✓ 视频已保存: {output_path}")

        return output_path

    def _extract_video_id(self, url: str) -> str:
        """从URL中提取视频ID"""
        # 简单的提取逻辑，可以根据需要扩展
        import hashlib

        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _extract_domain(self, url: str) -> str:
        """从URL中提取域名"""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc
        # 移除www前缀
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _extract_platform(self, url: str) -> str:
        """从URL中提取平台名称"""
        domain = self._extract_domain(url)
        # 常见的视频平台映射
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
            "bilibili.com": "bilibili",  # 虽然已经有专门的下载器，但这里也支持
            "youtube.com": "youtube",  # 虽然已经有专门的下载器，但这里也支持
            "youtu.be": "youtube",
        }

        for key, value in platform_map.items():
            if key in domain:
                return value

        # 如果没有匹配，返回域名
        return domain.split(".")[0] if "." in domain else domain

    @classmethod
    def match_url(cls, url: str) -> bool:
        """判断是否为其他视频链接（排除已支持的平台）"""
        # 排除已支持的平台（这些平台有专门的下载器）
        excluded_patterns = [
            r"douyin\.com",
            r"iesdouyin\.com",
            r"kuaishou\.com",
            r"xiaohongshu\.com",
            r"xhslink\.com",
            r"bilibili\.com",
            r"b23\.tv",
            r"youtube\.com",
            r"youtu\.be",
        ]

        # 如果匹配到排除的模式，返回False
        for pattern in excluded_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False

        # 常见的视频URL模式（包括TikTok）
        video_patterns = [
            r"\.mp4$",
            r"\.m3u8$",
            r"\.flv$",
            r"\.avi$",
            r"\.mov$",
            r"\.wmv$",
            r"\.webm$",
            r"video/",
            r"watch\?v=",
            r"/v/",
            r"vimeo\.com",
            r"twitter\.com",
            r"x\.com",
            r"instagram\.com",
            r"tiktok\.com",  # TikTok使用通用下载器
            r"twitch\.tv",
            r"dailymotion\.com",
            r"facebook\.com",
            r"nicovideo\.jp",
            r"t\.co/",  # Twitter短链接
            r"streamable\.com",
            r"gfycat\.com",
            r"reddit\.com.*/comments/.*/",  # Reddit视频
            r"imgur\.com",
            r"giphy\.com",
            r"tenor\.com",
            r"likee\.com",
            r"kwai\.com",
            r"snapchat\.com",
            r"pinterest\.com.*/pin/",
        ]

        # 检查是否为视频URL
        for pattern in video_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True

        # 默认返回True，尝试下载（作为兜底）
        return True
