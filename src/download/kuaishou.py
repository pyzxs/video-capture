"""快手视频下载器 - 参考 KS-Downloader 项目实现"""

import json
import re
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs

import aiofiles
import aiohttp
from lxml import etree
from tqdm import tqdm

from .base import BaseDownloader, VideoInfo


class KuaishouDownloader(BaseDownloader):
    """快手视频下载器

    参考 KS-Downloader 项目实现:
    - 通过短链接重定向获取真实 URL
    - 从网页 HTML 中提取 __APOLLO_STATE__ 数据
    - 解析视频下载链接
    """

    # PC 端 User-Agent
    PC_USERAGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    )

    # 移动端 User-Agent
    APP_USERAGENT = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
        "Mobile/15E148 Safari/604.1"
    )

    # PC 端页面请求头
    PC_PAGE_HEADERS = {
        "Origin": "https://www.kuaishou.com",
        "Referer": "https://www.kuaishou.com/new-reco",
        "User-Agent": PC_USERAGENT,
    }

    # PC 端数据请求头
    PC_DATA_HEADERS = {
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://www.kuaishou.com",
        "Referer": "https://www.kuaishou.com/new-reco?source=NewReco",
        "User-Agent": PC_USERAGENT,
    }

    # 下载请求头
    DOWNLOAD_HEADERS = {
        "User-Agent": PC_USERAGENT,
    }

    # URL 匹配正则
    # 快手短链接
    F_SHORT_URL = re.compile(
        r"(https?://\S*kuaishou\.(?:com|cn)/f/[^\s/\"<>\\^`{|}，。；！？、【】《》]+)"
    )
    V_SHORT_URL = re.compile(
        r"(https?://v\.kuaishou\.(?:com|cn)/[^\s/\"<>\\^`{|}，。；！？、【】《》]+)"
    )

    # 详情页 URL
    PC_DETAIL_URL = re.compile(r"(https?://\S*kuaishou\.(?:com|cn)/short-video/\S+)")
    C_DETAIL_URL = re.compile(r"(https?://\S*kuaishou\.(?:com|cn)/fw/photo/\S+)")
    REDIRECT_DETAIL_URL = re.compile(r"(https?://\S*chenzhongtech\.(?:com|cn)/fw/photo/\S+)")

    # 从 HTML 中提取数据的关键字
    WEB_KEYWORD = "window.__APOLLO_STATE__="

    def __init__(self, output_dir: Path = Path("./output")):
        super().__init__(output_dir)
        self._cookie: str = ""

    async def get_video_info(self, url: str) -> VideoInfo:
        """获取快手视频信息

        Args:
            url: 快手视频链接（支持短链接和详情链接）

        Returns:
            VideoInfo: 视频信息
        """
        # 1. 解析短链接，获取真实 URL
        real_url = await self._resolve_short_url(url)

        # 2. 从 URL 中提取参数
        web, user_id, photo_id = self._extract_params(real_url)

        if not photo_id:
            raise ValueError(f"无法从 URL 中提取视频 ID: {real_url}")

        # 3. 获取视频详情页 HTML
        html = await self._fetch_detail_page(real_url)

        # 4. 从 HTML 中提取视频数据
        video_data = self._extract_video_data(html, photo_id, web)

        if not video_data:
            raise ValueError("无法从网页中提取视频数据")

        # print(f"视频数据{video_data} {photo_id}")
        # 5. 构建 VideoInfo
        return VideoInfo(
            video_id=photo_id,
            title=video_data.get("caption", ""),
            url=video_data.get("download_url", ""),
            platform="kuaishou",
            author=video_data.get("author_name"),
            duration=self._parse_duration(video_data.get("duration", 0)),
            thumbnail=video_data.get("cover_url"),
            description=video_data.get("caption"),
            metadata=video_data,
        )

    async def download_video(self, video_info: VideoInfo, show_progress: bool = True) -> Path:
        """下载快手视频

        Args:
            video_info: 视频信息
            show_progress: 是否显示进度条

        Returns:
            Path: 下载后的文件路径
        """
        print("视频信息：{}".format(video_info))
        if not video_info.url:
            raise ValueError("视频下载链接为空")

        # 检查文件是否已存在
        existing_file = self._check_file_exists(video_info)
        if existing_file:
            if show_progress:
                print(f"✓ 视频已存在，跳过下载: {existing_file}")
            return existing_file

        output_path = self._get_video_filepath(video_info)

        # 临时文件
        temp_path = output_path.with_suffix(".tmp")

        async with aiohttp.ClientSession() as session:
            # 获取文件大小（支持断点续传）
            resume_pos = 0
            if temp_path.exists():
                resume_pos = temp_path.stat().st_size

            headers = self.DOWNLOAD_HEADERS.copy()
            if resume_pos > 0:
                headers["Range"] = f"bytes={resume_pos}-"

            async with session.get(video_info.url, headers=headers) as response:
                if response.status == 416:
                    # Range 请求失败，重新下载
                    temp_path.unlink(missing_ok=True)
                    resume_pos = 0
                    async with session.get(
                        video_info.url, headers=self.DOWNLOAD_HEADERS
                    ) as response:
                        response.raise_for_status()
                        await self._download_with_progress(
                            response, temp_path, 0, show_progress, video_info.title
                        )
                else:
                    response.raise_for_status()
                    await self._download_with_progress(
                        response, temp_path, resume_pos, show_progress, video_info.title
                    )

        # 重命名临时文件
        temp_path.rename(output_path)

        if show_progress:
            print(f"✓ 视频已保存: {output_path}")

        return output_path

    async def _download_with_progress(
        self,
        response: aiohttp.ClientResponse,
        temp_path: Path,
        resume_pos: int,
        show_progress: bool,
        title: str,
    ):
        """带进度条的下载"""
        total_size = int(response.headers.get("Content-Length", 0)) + resume_pos

        mode = "ab" if resume_pos > 0 else "wb"
        async with aiofiles.open(temp_path, mode) as f:
            if show_progress:
                with tqdm(
                    total=total_size,
                    initial=resume_pos,
                    unit="B",
                    unit_scale=True,
                    desc=f"下载 {title[:30]}",
                ) as pbar:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)
                        pbar.update(len(chunk))
            else:
                async for chunk in response.content.iter_chunked(1024 * 1024):
                    await f.write(chunk)

    @classmethod
    def match_url(cls, url: str) -> bool:
        """判断是否为快手链接"""
        patterns = [
            r"kuaishou\.com",
            r"kuaishou\.cn",
            r"chenzhongtech\.com",
            r"gifshow\.com",
            r"kwaicdn\.com",
        ]
        return any(re.search(p, url) for p in patterns)

    async def _resolve_short_url(self, url: str) -> str:
        """解析短链接，获取重定向后的真实 URL

        Args:
            url: 原始链接

        Returns:
            str: 重定向后的真实 URL
        """
        # 检查是否为短链接
        short_match = self.F_SHORT_URL.search(url) or self.V_SHORT_URL.search(url)

        if not short_match:
            # 不是短链接，直接返回
            return url

        short_url = short_match.group()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                short_url,
                headers=self.PC_PAGE_HEADERS,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                # 保存 cookie
                self._update_cookie(response.cookies)
                return str(response.url)

    def _update_cookie(self, cookies: SimpleCookie) -> None:
        """更新 cookie"""
        if self._cookie:
            return
        cookie_str = "; ".join([f"{key}={value.value}" for key, value in cookies.items()])
        if cookie_str:
            self._cookie = cookie_str

    def _extract_params(self, url: str) -> Tuple[bool, str, str]:
        """从 URL 中提取参数

        Args:
            url: 视频 URL

        Returns:
            Tuple[bool, str, str]: (是否为 PC 端, user_id, photo_id)
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # chenzhongtech 域名（移动端）
        if "chenzhongtech" in (parsed.hostname or ""):
            return (
                False,
                params.get("userId", [""])[0],
                params.get("photoId", [""])[0],
            )

        # short-video 或 fw/photo 路径（PC 端）
        if "short-video" in parsed.path or "fw/photo" in parsed.path:
            return (True, "", parsed.path.split("/")[-1])

        raise ValueError(f"无法解析 URL: {url}")

    async def _fetch_detail_page(self, url: str) -> str:
        """获取视频详情页 HTML

        Args:
            url: 视频 URL

        Returns:
            str: HTML 内容
        """
        headers = self.PC_PAGE_HEADERS.copy()
        if self._cookie:
            headers["Cookie"] = self._cookie

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response.raise_for_status()
                return await response.text()

    def _extract_video_data(self, html: str, photo_id: str, web: bool) -> Optional[dict]:
        """从 HTML 中提取视频数据

        Args:
            html: HTML 内容
            photo_id: 视频 ID
            web: 是否为 PC 端

        Returns:
            Optional[dict]: 视频数据
        """
        if not html:
            return None

        # 提取 __APOLLO_STATE__ 数据
        script_data = self._extract_script_data(html)
        if not script_data:
            return None

        try:
            data = json.loads(script_data)
        except json.JSONDecodeError:
            return None

        if web:
            return self._parse_web_data(data, photo_id)
        else:
            return self._parse_app_data(data, photo_id)

    def _extract_script_data(self, html: str) -> Optional[str]:
        """从 HTML 中提取 script 数据

        参考 KS-Downloader 的实现：
        - 使用 lxml 解析 HTML
        - 用 xpath 获取 script 标签内容
        - 去掉 window.__APOLLO_STATE__= 前缀
        - 去掉末尾的 ;(function(){...}());
        """
        if not html:
            return None

        try:
            # 使用 lxml 解析 HTML
            tree = etree.HTML(html)
            if tree is None:
                return None

            # 获取所有 script 标签的文本内容
            scripts = tree.xpath("//script/text()")
            if not scripts:
                return None

            # 查找包含 __APOLLO_STATE__ 的 script
            for script in scripts:
                if self.WEB_KEYWORD in script:
                    # 提取数据
                    text = script.lstrip(self.WEB_KEYWORD)
                    # 去掉末尾的自执行函数
                    text = text.replace(
                        ";(function(){var s;(s=document.currentScript||document.scripts["
                        "document.scripts.length-1]).parentNode.removeChild(s);}());",
                        "",
                    )
                    return text.strip()

            return None
        except Exception:
            return None

    def _parse_web_data(self, data: dict, photo_id: str) -> Optional[dict]:
        """解析 PC 端数据"""
        try:
            # 获取 defaultClient
            default_client = data.get("defaultClient", {})

            # 视频 detail key
            detail_key = f"VisionVideoDetailPhoto:{photo_id}"
            detail = default_client.get(detail_key, {})

            if not detail:
                return None

            # 获取作者信息
            author_name = ""
            for key, value in default_client.items():
                if "VisionVideoDetailAuthor:" in key:
                    author_name = value.get("name", "")
                    break

            return {
                "photo_type": "视频",
                "caption": detail.get("caption", ""),
                "cover_url": detail.get("coverUrl", ""),
                "duration": detail.get("duration", 0),
                "like_count": detail.get("realLikeCount", 0),
                "view_count": detail.get("viewCount", 0),
                "timestamp": detail.get("timestamp", 0),
                "download_url": detail.get("photoUrl", ""),
                "author_name": author_name,
            }
        except Exception:
            return None

    def _parse_app_data(self, data: dict, photo_id: str) -> Optional[dict]:
        """解析移动端数据"""
        try:
            photo = data.get("photo", {})
            if not photo:
                return None

            # 获取封面 URL
            cover_urls = photo.get("coverUrls", [])
            cover_url = cover_urls[0].get("url", "") if cover_urls else ""

            # 获取下载 URL
            download_urls = []
            ext_params = photo.get("ext_params", {})
            atlas = ext_params.get("atlas", {})
            cdn = atlas.get("cdn", [])
            atlas_list = atlas.get("list", [])

            if cdn and atlas_list:
                cdn_host = cdn[0] if isinstance(cdn, list) else cdn
                download_urls = [f"https://{cdn_host}{item}" for item in atlas_list]

            # 如果是视频，尝试获取视频 URL
            if not download_urls:
                # 尝试从其他字段获取
                download_urls = [photo.get("playUrl", "")]

            return {
                "photo_type": "图片" if ext_params.get("single") else "视频",
                "caption": photo.get("caption", ""),
                "cover_url": cover_url,
                "duration": photo.get("duration", 0),
                "like_count": photo.get("likeCount", 0),
                "view_count": photo.get("viewCount", 0),
                "timestamp": photo.get("timestamp", 0),
                "download_url": download_urls[0] if download_urls else "",
                "download_urls": download_urls,
                "author_name": photo.get("userName", ""),
            }
        except Exception:
            return None

    @staticmethod
    def _parse_duration(duration_ms: int) -> int:
        """解析时长（毫秒转秒）"""
        return duration_ms // 1000 if duration_ms else 0


# 类型导入
