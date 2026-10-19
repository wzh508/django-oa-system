"""类型化业务异常 + 全局异常转译。

业务异常 → 400，未认证 → 401，越权 → 403，未找到 → 404，服务端异常 → 500 且不回传堆栈。
"""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied as DRFPermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class ErrorCode:
    OK = 0
    BAD_REQUEST = 400
    BUSINESS_ERROR = 4000
    NOT_AUTHENTICATED = 401
    TOKEN_EXPIRED = 4010
    PERMISSION_DENIED = 403
    DATA_SCOPE_DENIED = 4031
    NOT_FOUND = 404
    CONFLICT = 409
    RATE_LIMITED = 429
    INTERNAL = 500


class BusinessException(APIException):
    """业务异常基类：默认 400。"""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "业务处理失败"
    default_code = ErrorCode.BUSINESS_ERROR

    def __init__(self, detail=None, code=None, status_code=None):
        self.code = code if code is not None else self.default_code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=detail)


class PermissionDeniedException(BusinessException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "无权限执行该操作"
    default_code = ErrorCode.PERMISSION_DENIED


class DataScopeDeniedException(BusinessException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "数据不在可访问范围内"
    default_code = ErrorCode.DATA_SCOPE_DENIED


class NotFoundException(BusinessException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "资源不存在"
    default_code = ErrorCode.NOT_FOUND


class ConflictException(BusinessException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "资源状态冲突"
    default_code = ErrorCode.CONFLICT


def _flatten(detail) -> str:
    """把 DRF 的嵌套校验错误拍平成一句可读中文。"""
    if isinstance(detail, list):
        return "；".join(_flatten(d) for d in detail)
    if isinstance(detail, dict):
        parts = []
        for k, v in detail.items():
            key = "参数" if k in ("detail", "non_field_errors") else str(k)
            parts.append(f"{key}: {_flatten(v)}")
        return "；".join(parts)
    return str(detail)


def custom_exception_handler(exc, context):
    """统一异常转译，输出 {code, msg, data}。"""
    request = context.get("request")
    view = context.get("view")

    if isinstance(exc, BusinessException):
        logger.warning("business error: %s", exc.detail)
        return Response({"code": exc.code, "msg": _flatten(exc.detail), "data": None}, status=exc.status_code)

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        code = ErrorCode.TOKEN_EXPIRED if "expire" in str(exc.detail).lower() else ErrorCode.NOT_AUTHENTICATED
        return Response({"code": code, "msg": "登录已失效，请重新登录", "data": None}, status=401)

    if isinstance(exc, (DRFPermissionDenied, DjangoPermissionDenied)):
        return Response({"code": ErrorCode.PERMISSION_DENIED, "msg": _flatten(exc.detail), "data": None}, status=403)

    if isinstance(exc, Http404):
        return Response({"code": ErrorCode.NOT_FOUND, "msg": "资源不存在", "data": None}, status=404)

    if isinstance(exc, ValidationError):
        return Response({"code": ErrorCode.BAD_REQUEST, "msg": _flatten(exc.detail), "data": None}, status=400)

    response = drf_exception_handler(exc, context)
    if response is not None:
        return Response(
            {"code": response.status_code * 100 if response.status_code < 100 else response.status_code,
             "msg": _flatten(response.data),
             "data": None},
            status=response.status_code,
        )

    logger.exception(
        "unhandled exception: view=%s path=%s",
        getattr(view, "__class__", type("", (), {"__name__": "?"})()).__class__.__name__,
        getattr(request, "path", "-"),
    )
    return Response({"code": ErrorCode.INTERNAL, "msg": "服务器内部错误", "data": None}, status=500)
