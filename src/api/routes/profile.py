"""用户信息代理：从 CMS 获取用户资料和消耗记录。"""
import requests
from fastapi import APIRouter, Query, HTTPException
from src.config import get_config

router = APIRouter(prefix="/profile", tags=["用户信息"])


def _cms_get(path: str, params: dict | None = None) -> dict:
    """向 CMS 发起 GET 请求，返回 JSON data 字段。"""
    api_key = get_config("api_key")
    cms_url = get_config("cms_base_url")
    if not api_key:
        raise HTTPException(502, "未注册 CMS 用户")
    try:
        resp = requests.get(
            f"{cms_url}{path}",
            headers={"X-Api-Key": api_key},
            params=params or {},
            timeout=15,
        )
        if resp.status_code >= 400:
            raise HTTPException(502, f"CMS 返回错误 ({resp.status_code}): {resp.text[:200]}")
        return resp.json().get("data", {})
    except requests.RequestException as e:
        raise HTTPException(502, f"无法连接 CMS: {e}")


@router.get("")
def get_profile():
    """获取当前用户信息（user_id, api_key, 剩余额度等）。"""
    return _cms_get("/api/me")


@router.get("/records")
def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取当前用户的消耗记录列表。"""
    return _cms_get("/api/me/records", {"page": page, "page_size": page_size})
