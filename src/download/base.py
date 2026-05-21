"""基础下载器抽象类"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import aiohttp


@dataclass
class VideoInfo:
    """视频信息数据类"""

    video_id: str
    title: str
    url: str
    platform: str
    author: Optional[str] = None
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseDownloader(ABC):
    """下载器基类"""

    def __init__(self, output_dir: Path = Path("./output")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def get_video_info(self, url: str) -> VideoInfo:
        """获取视频信息"""
        pass

    @abstractmethod
    async def download_video(
        self,
        video_info: VideoInfo,
        show_progress: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Path:
        """下载视频"""
        pass

    @classmethod
    @abstractmethod
    def match_url(cls, url: str) -> bool:
        """判断是否支持该URL"""
        pass

    @property
    def _headers(self) -> dict:
        """默认请求头，子类可覆盖。"""
        return {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    async def _download_bytes_with_retry(
        self, url: str, headers: Optional[dict] = None, max_retries: int = 3,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> bytes:
        """带重试的字节下载，处理 ContentLengthError 等网络异常。"""
        headers = headers or self._headers
        last_error = None

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status != 200:
                            raise Exception(f"下载失败: HTTP {response.status}")
                        if progress_callback:
                            total = int(response.headers.get("Content-Length", 0))
                            chunks = []
                            downloaded = 0
                            async for chunk in response.content.iter_chunked(512 * 1024):
                                chunks.append(chunk)
                                downloaded += len(chunk)
                                if total > 0:
                                    progress_callback(min(99, int(downloaded * 100 / total)))
                            progress_callback(100)
                            return b"".join(chunks)
                        return await response.read()
            except (aiohttp.ClientPayloadError, aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 2  # 2s, 4s, then give up
                    print(f"[retry] 下载失败 (尝试 {attempt + 1}/{max_retries})，{wait}s 后重试: {e}")
                    await asyncio.sleep(wait)

        raise Exception(f"下载失败（已重试 {max_retries} 次）: {last_error}")

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名中的非法字符"""
        import re

        name = re.sub(r'[\\/:*?"<>|]', "_", name)
        return name[:200]

    def _find_downloaded_file(self, basename: str) -> Optional[Path]:
        """下载完成后查找输出文件（依次尝试精确扩展名、模糊匹配、最新文件）"""
        # 1. 精确扩展名匹配
        for ext in (".mp4", ".flv", ".mkv", ".webm"):
            candidate = self.output_dir / f"{basename}{ext}"
            if candidate.exists():
                return candidate

        # 2. 模糊匹配
        for file in self.output_dir.glob(f"{basename}.*"):
            if file.is_file():
                return file

        # 3. 最后手段：找最新的媒体文件并重命名
        best = None
        best_mtime = 0
        for file in self.output_dir.iterdir():
            if file.is_file() and file.suffix in ('.mp4', '.flv', '.mkv', '.webm', '.mp3'):
                try:
                    mtime = file.stat().st_mtime
                    if mtime > best_mtime:
                        best_mtime = mtime
                        best = file
                except OSError:
                    continue

        if best:
            new_path = self.output_dir / f"{basename}{best.suffix}"
            best.rename(new_path)
            return new_path

        return None

    def _get_video_filepath(self, video_info: VideoInfo, extension: str = ".mp4") -> Path:
        """获取视频文件路径"""
        # 使用平台和视频ID作为文件名
        filename = f"{video_info.platform}_{video_info.video_id}{extension}"
        return self.output_dir / filename

    def _check_file_exists(self, video_info: VideoInfo, extension: str = ".mp4") -> Optional[Path]:
        """检查文件是否已存在，如果存在则返回文件路径"""
        # 首先尝试标准文件名
        standard_path = self._get_video_filepath(video_info, extension)
        if standard_path.exists():
            return standard_path

        # 如果没有找到，尝试查找以平台和视频ID开头的文件
        pattern = f"{video_info.platform}_{video_info.video_id}.*"
        for file in self.output_dir.glob(pattern):
            if file.is_file():
                return file

        return None
