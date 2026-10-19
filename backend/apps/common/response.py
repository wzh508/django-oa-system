"""统一响应体。

成功：{"code": 0, "msg": "ok", "data": {...}}
失败：{"code": <非0>, "msg": "<错误说明>", "data": null}
"""
from typing import Any

from rest_framework.response import Response


class ApiResponse(Response):
    """统一响应封装。"""

    def __init__(self, code: int = 0, msg: str = "ok", data: Any = None, status: int | None = None, **kwargs):
        payload = {"code": code, "msg": msg, "data": data}
        payload.update(kwargs)
        super().__init__(payload, status=status)


def ok(data: Any = None, msg: str = "ok", status: int = 200) -> ApiResponse:
    return ApiResponse(code=0, msg=msg, data=data, status=status)


def created(data: Any = None, msg: str = "创建成功") -> ApiResponse:
    return ApiResponse(code=0, msg=msg, data=data, status=201)


def no_content(msg: str = "删除成功") -> ApiResponse:
    return ApiResponse(code=0, msg=msg, data=None, status=204)


def fail(msg: str = "请求失败", code: int = 400, status: int = 400, data: Any = None) -> ApiResponse:
    return ApiResponse(code=code, msg=msg, data=data, status=status)
