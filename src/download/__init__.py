"""视频下载器模块"""

from .base import BaseDownloader, VideoInfo
from .bilibili import BilibiliDownloader
from .douyin import DouyinDownloader
from .kuaishou import KuaishouDownloader
from .other import OtherDownloader
from .xiaohongshu import XiaohongshuDownloader
from .youtube import YouTubeDownloader

__all__ = [
    "BaseDownloader",
    "VideoInfo",
    "DouyinDownloader",
    "KuaishouDownloader",
    "XiaohongshuDownloader",
    "BilibiliDownloader",
    "YouTubeDownloader",
    "OtherDownloader",
]
