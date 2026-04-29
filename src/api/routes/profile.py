"""用户信息代理：从 CMS 获取用户资料和消耗记录。"""
import requests
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from src.config import get_config

router = APIRouter(prefix="/profile", tags=["用户信息"])


class RechargeBody(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)


def _cms_call(method: str, path: str, params: dict | None = None, json_body: dict | None = None) -> dict:
    """向 CMS 发起请求，返回 JSON data 字段。"""
    api_key = get_config("api_key")
    cms_url = get_config("cms_base_url")
    if not api_key:
        raise HTTPException(502, "未注册 CMS 用户")
    try:
        resp = requests.request(
            method,
            f"{cms_url}{path}",
            headers={"X-Api-Key": api_key},
            params=params or {},
            json=json_body,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code >= 400:
            raise HTTPException(502, data.get("message", f"CMS 返回错误 ({resp.status_code})"))
        return data.get("data", data)
    except requests.RequestException as e:
        raise HTTPException(502, f"无法连接 CMS: {e}")


@router.get("")
def get_profile():
    """获取当前用户信息（user_id, api_key, 剩余额度等）。"""
    return _cms_call("GET", "/api/me")


@router.get("/records")
def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取当前用户的消耗记录列表。"""
    return _cms_call("GET", "/api/me/records", {"page": page, "page_size": page_size})


@router.post("/recharge")
def recharge(body: RechargeBody):
    """使用充值码充值。"""
    return _cms_call("POST", "/api/me/recharge", json_body={"code": body.code})
