from typing import Any

from fastapi import HTTPException
from starlette.responses import JSONResponse


def response_success(*, data: Any = None, message: str = "Success", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": status_code,
            "message": message,
            "data": data,
        },
    )


def fail_response(*, status_code: int = 400, message: str = "Bad Request") -> HTTPException:
    """使用方式：raise fail_response(status_code=404, message='资源不存在')"""
    return HTTPException(
        status_code=status_code,
        detail={
            "code": status_code,
            "message": message,
            "data": None,
        },
    )
