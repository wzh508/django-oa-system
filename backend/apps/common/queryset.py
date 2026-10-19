"""数据范围过滤 Mixin：按用户数据范围自动过滤 queryset。

用法：
    class XxxViewSet(DataScopeMixin, ModelViewSet):
        data_scope_resource = "attendance.record"
"""
from rest_framework.exceptions import PermissionDenied

from apps.accounts.services import get_data_scope_q, resolve_data_scope_expr


class DataScopeMixin:
    """重写 get_queryset()，把声明式数据范围表达式解析为 ORM Q 对象。"""

    #: 资源标识，形如 "attendance.record"，用于定位角色上配置的数据范围规则
    data_scope_resource: str | None = None
    #: 表达式中引用当前用户的占位符映射
    data_scope_user_field = "created_by"

    def get_queryset(self):
        qs = super().get_queryset()  # type: ignore[misc]
        user = getattr(self.request, "user", None)
        if user is None:
            return qs
        if getattr(user, "is_superuser", False):
            return qs
        if self.data_scope_resource is None:
            return qs
        try:
            q = get_data_scope_q(user, self.data_scope_resource, user_field=self.data_scope_user_field)
        except PermissionDenied:
            return qs.none()
        if q is None:
            return qs
        return qs.filter(q)

    def check_object_against_scope(self, obj):
        """对象级数据范围校验，用于 retrieve/update/destroy。"""
        user = getattr(self.request, "user", None)
        if user is None or getattr(user, "is_superuser", False):
            return
        if not self.data_scope_resource:
            return
        q = get_data_scope_q(user, self.data_scope_resource, user_field=self.data_scope_user_field)
        if q is None:
            return
        model = obj._meta.model
        if not model.objects.filter(q).filter(pk=obj.pk).exists():
            raise PermissionDenied("数据不在可访问范围内")


__all__ = ["DataScopeMixin", "resolve_data_scope_expr"]
