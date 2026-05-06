"""共享 HTTP 客户端：requests.Session 连接池（同步）+ aiohttp（异步）。"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── 同步 Session（线程安全，连接池复用） ──

_JSON = dict[str, Any] | list[Any]

_retry = Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 502, 503, 504])
_adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=_retry)

_sync_session: requests.Session | None = None


def _get_sync_session() -> requests.Session:
    global _sync_session
    if _sync_session is None:
        _sync_session = requests.Session()
        _sync_session.mount("https://", _adapter)
        _sync_session.mount("http://", _adapter)
    return _sync_session


def sync_post(url: str, json: _JSON, headers: dict[str, str], timeout: int = 30) -> requests.Response:
    return _get_sync_session().post(url, json=json, headers=headers, timeout=timeout)


def sync_get(url: str, headers: dict[str, str], timeout: int = 30) -> requests.Response:
    return _get_sync_session().get(url, headers=headers, timeout=timeout)


# ── 异步 Session（用于 async def 路由） ──

_async_session: aiohttp.ClientSession | None = None
_async_lock = asyncio.Lock()


async def _get_async_session() -> aiohttp.ClientSession:
    global _async_session
    if _async_session is None:
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300, force_close=False)
        timeout = aiohttp.ClientTimeout(total=120)
        _async_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _async_session


async def async_post(
    url: str, json: _JSON, headers: dict[str, str], timeout: int = 120
) -> tuple[int, _JSON, dict[str, str]]:
    """返回 (status_code, json_body, response_headers)。"""
    session = await _get_async_session()
    async with session.post(
        url, json=json, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
    ) as resp:
        data: _JSON = await resp.json()
        return resp.status, data, dict(resp.headers)
