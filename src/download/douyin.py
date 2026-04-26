"""抖音视频下载器"""

import json
import re
from pathlib import Path
from typing import Optional

import aiohttp

from .base import BaseDownloader, VideoInfo


class DouyinDownloader(BaseDownloader):
    """抖音视频下载器"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取抖音视频信息"""
        # 解析短链接或直接ID
        modal_id = self._extract_modal_id(url)
        if not modal_id:
            # 如果是分享链接，先请求获取重定向
            modal_id = await self._resolve_share_url(url)

        return await self._get_info_by_modal_id(modal_id)

    async def download_video(self, video_info: VideoInfo, show_progress: bool = True) -> Path:
        """下载抖音视频"""
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
        """判断是否为抖音链接"""
        patterns = [
            r"douyin\.com",
            r"iesdouyin\.com",
            r"v\.douyin\.com",
        ]
        return any(re.search(p, url) for p in patterns)

    def _extract_modal_id(self, url: str) -> Optional[str]:
        """提取视频ID"""
        # 匹配16位以上数字
        match = re.search(r"(\d{16,})", url)
        return match.group(1) if match else None

    async def _resolve_share_url(self, url: str) -> str:
        """解析分享链接获取视频ID"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.HEADERS, allow_redirects=False) as response:
                if response.status in (301, 302):
                    location = response.headers.get("Location")
                    if location:
                        match = re.search(r"/video/(\d+)", location)
                        if match:
                            return match.group(1)

        raise Exception("无法解析抖音分享链接")

    async def _get_info_by_modal_id(self, modal_id: str) -> VideoInfo:
        """通过视频ID获取信息"""
        page_url = f"https://www.iesdouyin.com/share/video/{modal_id}/"

        async with aiohttp.ClientSession() as session:
            async with session.get(page_url, headers=self.HEADERS) as response:
                html = await response.text()

                # 提取 window._ROUTER_DATA
                match = re.search(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", html)
                if not match:
                    raise Exception("无法解析视频信息")

                data = json.loads(match.group(1).strip())
                loader_data = data.get("loaderData", data)

                # 提取视频数据
                video_data = None
                for key in ["video_(id)/page", "note_(id)/page"]:
                    if key in loader_data:
                        items = loader_data[key].get("videoInfoRes", {}).get("item_list", [])
                        if items:
                            video_data = items[0]
                            break

                if not video_data:
                    raise Exception("无法获取视频数据")

                # 获取视频URL
                video_url = (
                    video_data.get("video", {}).get("play_addr", {}).get("url_list", [None])[0]
                )
                if video_url:
                    video_url = video_url.replace("playwm", "play")
                if not video_url:
                    video_url = (
                        video_data.get("video", {})
                        .get("download_addr", {})
                        .get("url_list", [None])[0]
                    )

                title = video_data.get("desc", f"douyin_{modal_id}")

                return VideoInfo(
                    video_id=modal_id,
                    title=self._sanitize_filename(title),
                    url=video_url,
                    platform="douyin",
                    author=video_data.get("author", {}).get("nickname"),
                    description=title[:500],
                )
