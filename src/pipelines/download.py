"""视频下载流水线： 视频真实地址 → 下载 → 音频 → 文本。"""
from pathlib import Path
from typing import Callable, Optional, Tuple

from src.config import get_config
from src.download import BaseDownloader, DouyinDownloader, KuaishouDownloader, XiaohongshuDownloader, \
    BilibiliDownloader, YouTubeDownloader, OtherDownloader, VideoInfo
from src.logger import get_logger
from src.utils import ensure_date_dir

_logger = get_logger("download")

downloaders = [
    DouyinDownloader,
    KuaishouDownloader,
    XiaohongshuDownloader,
    BilibiliDownloader,
    YouTubeDownloader,
    OtherDownloader,
]


def get_downloader(query: str, output_dir: Path, proxy: Optional[str] = None) -> Optional[
    BaseDownloader]:
    """根据URL获取合适的下载器"""
    for downloader_class in downloaders:
        if downloader_class.match_url(query):
            downloader = downloader_class(output_dir)
            if proxy:
                if isinstance(downloader, YouTubeDownloader):
                    downloader.proxy = proxy
                    downloader.ydl_opts["proxy"] = proxy
                elif isinstance(downloader, OtherDownloader):
                    downloader.proxy = proxy
                    downloader.ydl_opts["proxy"] = proxy
            return downloader
    return None


async def process_download(
    query: str,
    output_dir: Path,
    proxy: Optional[str] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> tuple[VideoInfo, Path]:
    """处理视频"""
    downloader = get_downloader(query, output_dir, proxy)
    if not downloader:
        raise Exception(f"不支持的URL: {query}")

    print(f"[OK] 识别到平台: {downloader.__class__.__name__.replace('Downloader', '')}")

    video_info = await downloader.get_video_info(query)
    print(f"[OK] 视频标题: {video_info.title}")

    video_path = await downloader.download_video(video_info, progress_callback=progress_callback)

    return video_info, video_path
