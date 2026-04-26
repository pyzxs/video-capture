"""B站视频下载器"""

import asyncio
import re
from pathlib import Path
from typing import Optional

import aiohttp

from .base import BaseDownloader, VideoInfo
from ..config import BASE_DIR

you_get_prefix = f"{BASE_DIR}/bin/"

class BilibiliDownloader(BaseDownloader):
    """B站视频下载器（基于 you-get）"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com",
    }

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取B站视频信息"""
        bvid = self._extract_bvid(url)
        return await self._get_info_by_bvid(bvid)

    async def download_video(self, video_info: VideoInfo, show_progress: bool = True) -> Path:
        """使用 you-get 下载B站视频"""
        # 检查文件是否已存在
        existing_file = self._check_file_exists(video_info)
        if existing_file:
            if show_progress:
                print(f"✓ 视频已存在，跳过下载: {existing_file}")
            return existing_file

        # 确保输出目录存在
        output_dir = self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # 使用基类方法获取文件名
        output_path = self._get_video_filepath(video_info)
        output_basename = output_path.stem

        cmd = [
            f"{you_get_prefix}you-get",
            "--debug",
            # "--json",
            "-o",
            str(output_dir),
            "-O",
            output_basename,
            video_info.url,
        ]

        if show_progress:
            print(f"正在使用 you-get 下载: {video_info.title}")
            # 让 you-get 输出到控制台
            stdout_handle = None
            stderr_handle = None
        else:
            # 静默模式，抑制输出
            stdout_handle = asyncio.subprocess.PIPE
            stderr_handle = asyncio.subprocess.PIPE

        # 异步执行 you-get
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=stdout_handle, stderr=stderr_handle
        )

        # 等待完成
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="ignore") if stderr else "unknown error"
            raise Exception(f"you-get 下载失败 (code {process.returncode}): {error_msg[:500]}")

        possible_extensions = [".mp4", ".flv", ".mkv", ".webm"]
        downloaded_file = None
        for ext in possible_extensions:
            candidate = output_dir / f"{output_basename}{ext}"
            if candidate.exists():
                downloaded_file = candidate
                break

        if not downloaded_file:
            # 尝试查找以输出文件名开头的任意文件
            for file in output_dir.glob(f"{output_basename}.*"):
                downloaded_file = file
                break

        if not downloaded_file:
            raise Exception("下载完成但未找到输出文件")

        if show_progress:
            print(f"✓ 视频已保存: {downloaded_file}")

        xml_filename = Path(output_dir / f"{video_info.title}.cmt.xml")
        if xml_filename.exists():
            xml_filename.unlink()
            print("✅ 清理测试视频文件")

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
        # 匹配BV号
        match = re.search(r"BV\w+", url)
        if match:
            return match.group(0)

        # 匹配AV号
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

                # 获取视频URL
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
