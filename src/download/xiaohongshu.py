"""小红书视频下载器"""

import re
from pathlib import Path

import aiohttp

from .base import BaseDownloader, VideoInfo


class XiaohongshuDownloader(BaseDownloader):
    """小红书视频下载器"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15",
    }

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取小红书视频信息"""
        note_id = await self._extract_note_id(url)
        return await self._get_info_by_note_id(note_id)

    async def download_video(self, video_info: VideoInfo, show_progress: bool = True) -> Path:
        """下载小红书视频"""
        # 检查文件是否已存在
        existing_file = self._check_file_exists(video_info)
        if existing_file:
            if show_progress:
                print(f"✓ 视频已存在，跳过下载: {existing_file}")
            return existing_file

        output_path = self._get_video_filepath(video_info)

        async with aiohttp.ClientSession() as session:
            async with session.get(video_info.url, headers=self.HEADERS) as response:
                if response.status != 200:
                    raise Exception(f"下载失败: HTTP {response.status}")

                output_path.write_bytes(await response.read())

                if show_progress:
                    print(f"✓ 视频已保存: {output_path}")

                return output_path

    @classmethod
    def match_url(cls, url: str) -> bool:
        """判断是否为小红书链接"""
        patterns = [
            r"xiaohongshu\.com",
            r"xhslink\.com",
        ]
        return any(re.search(p, url) for p in patterns)

    async def _extract_note_id(self, url: str) -> str:
        """提取笔记ID"""
        # 直接匹配
        match = re.search(r"/discovery/item/(\w+)", url)
        if match:
            return match.group(1)

        # 处理短链接
        if "xhslink.com" in url:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=self.HEADERS, allow_redirects=False
                ) as response:
                    if response.status in (301, 302):
                        location = response.headers.get("Location")
                        if location:
                            match = re.search(r"/discovery/item/(\w+)", location)
                            if match:
                                return match.group(1)

        raise Exception("无法提取小红书笔记ID")

    async def _get_info_by_note_id(self, note_id: str) -> VideoInfo:
        """通过笔记ID获取信息"""
        api_url = f"https://www.xiaohongshu.com/fe_api/burdock/weixin/v2/note/{note_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=self.HEADERS) as response:
                data = await response.json()
                note_data = data.get("data", {}).get("note", {})

                if not note_data:
                    raise Exception("无法获取视频信息")

                video_list = (
                    note_data.get("video", {}).get("media", {}).get("stream", {}).get("h264", [])
                )
                video_url = video_list[0].get("master_url") if video_list else None

                if not video_url:
                    # 尝试其他格式
                    video_url = note_data.get("video", {}).get("url")

                return VideoInfo(
                    video_id=note_id,
                    title=self._sanitize_filename(note_data.get("title", f"xiaohongshu_{note_id}")),
                    url=video_url,
                    platform="xiaohongshu",
                    author=note_data.get("user", {}).get("nickname"),
                    description=note_data.get("desc", "")[:500],
                )
