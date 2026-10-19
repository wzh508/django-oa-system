"""通用 ViewSet 基类：权限码自动推导 + 操作日志哈希链留痕。"""
import logging
import time

from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.exceptions import PermissionDeniedException
from apps.common.hashchain import GENESIS_HASH, build_record

logger = logging.getLogger(__name__)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SENSITIVE_ACTIONS = {"destroy", "export", "grant_permission", "view_plaintext", "change_password"}


def client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class AuditLogMixin:
    """写操作自动记录操作日志（哈希链）。"""

    audit_enabled = True

    def _audit_module(self) -> str:
        return getattr(self, "audit_module", "") or self.__class__.__name__.replace("ViewSet", "").lower()

    def _audit_action(self) -> str:
        action = getattr(self, "action", None)
        if action:
            return action
        return {"POST": "create", "PUT": "update", "PATCH": "partial_update", "DELETE": "destroy"}.get(
            self.request.method, self.request.method.lower()
        )

    def _write_operation_log(self, request, response, cost_ms: int) -> None:
        if not self.audit_enabled or request.method not in WRITE_METHODS:
            return
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        params = None
        try:
            if request.method in ("POST", "PUT", "PATCH"):
                data = getattr(request, "data", None)
                if isinstance(data, dict):
                    params = {k: str(v)[:200] for k, v in data.items() if k.lower() not in ("password", "old_password", "new_password")}
            else:
                params = dict(request.GET.items()) or None
        except Exception:
            params = None

        record = {
            "module": self._audit_module(),
            "action": self._audit_action(),
            "method": request.method,
            "path": request.path,
            "params": params,
            "username": user.username if user else "",
            "ip": client_ip(request),
            "ua": request.META.get("HTTP_USER_AGENT", "")[:200],
            "status_code": getattr(response, "status_code", 0),
            "cost_ms": cost_ms,
            "created_at": timezone.now().isoformat(),
        }
        try:
            from apps.accounts.models import OperationLog  # 延迟导入，避免 common 反向依赖业务 app

            with transaction.atomic():
                last = OperationLog.objects.select_for_update().order_by("-id").first()
                prev = last.curr_hash if last else GENESIS_HASH
                curr_hash, content = build_record(prev, **record)
                OperationLog.objects.create(
                    user=user,
                    username=record["username"],
                    module=record["module"],
                    action=record["action"],
                    method=record["method"],
                    path=record["path"],
                    params=record["params"],
                    ip=record["ip"],
                    ua=record["ua"],
                    status_code=record["status_code"],
                    cost_ms=record["cost_ms"],
                    sensitive=self._audit_action() in SENSITIVE_ACTIONS,
                    prev_hash=prev,
                    curr_hash=curr_hash,
                    content=content,
                )
        except Exception as exc:
            logger.warning("write operation log failed: %s", exc)

    def finalize_response(self, request, response, *args, **kwargs):
        resp = super().finalize_response(request, response, *args, **kwargs)
        # 统一响应体：DRF 标准响应（list/retrieve/create/update）在此包装为 {code,msg,data}
        data = getattr(resp, "data", None)
        if resp.status_code < 400 and isinstance(data, (dict, list)):
            already = isinstance(data, dict) and "code" in data and "data" in data
            if not already:
                resp.data = {"code": 0, "msg": "ok", "data": data}
        cost = int((time.time() - getattr(request, "_start_at", time.time())) * 1000)
        try:
            self._write_operation_log(request, resp, cost)
        except Exception:
            pass
        return resp


class PermCodeMixin:
    """按 action 自动推导权限码，接口默认拒绝。"""

    perm_prefix: str = ""        # 如 "accounts:user"
    perm_map: dict = {}          # 覆盖：{"list": "xxx:yyy"}
    #: 放行白名单（不校验权限码，仅要求登录）
    open_actions: set = set()

    def get_perm_code(self) -> str | None:
        action = getattr(self, "action", None) or ""
        if action in self.perm_map:
            return self.perm_map[action]
        if action in self.open_actions:
            return None
        if self.perm_prefix:
            return f"{self.perm_prefix}:{action}"
        return None

    def get_permissions(self):
        from apps.common.permissions import HasPerm

        code = self.get_perm_code()
        if code is None:
            return [IsAuthenticated()]
        return [HasPerm(code)]


class BaseViewSet(AuditLogMixin, PermCodeMixin, viewsets.GenericViewSet):
    """业务 ViewSet 统一基类。"""

    def check_data_scope(self, obj) -> None:
        from apps.common.queryset import DataScopeMixin

        if isinstance(self, DataScopeMixin):
            self.check_object_against_scope(obj)

    def get_object(self):
        obj = super().get_object()
        self.check_data_scope(obj)
        return obj


class BaseModelViewSet(AuditLogMixin, PermCodeMixin, viewsets.ModelViewSet):
    """带完整 CRUD 的基类。"""

    def perform_destroy(self, instance):
        if hasattr(instance, "soft_delete"):
            instance.created_by = instance.created_by  # 保持引用
            instance.soft_delete()
        else:
            instance.delete()
