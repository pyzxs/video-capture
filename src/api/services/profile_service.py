"""Profile business logic: CMS proxy for user info, records, recharge."""
import requests

from src.api.response import fail_response
from src.config import get_config


def _cms_call(method: str, path: str, params: dict | None = None, json_body: dict | None = None, unwrap: bool = True) -> dict:
    api_key = get_config("api_key")
    cms_url = get_config("cms_base_url")
    if not api_key:
        raise fail_response(status_code=502, message="未注册 CMS 用户")
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
            raise fail_response(status_code=502, message=data.get("message", f"CMS 返回错误 ({resp.status_code})"))
        if unwrap:
            return data.get("data", data)
        return data
    except requests.RequestException as e:
        raise fail_response(status_code=502, message=f"无法连接 CMS: {e}")


def get_profile() -> dict:
    return _cms_call("GET", "/api/me")


def get_records(page: int = 1, page_size: int = 20) -> dict:
    return _cms_call("GET", "/api/me/records", {"page": page, "page_size": page_size}, unwrap=False)


def recharge(code: str) -> dict:
    return _cms_call("POST", "/api/me/recharge", json_body={"code": code})
