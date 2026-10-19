"""DRF 权限类：接口级权限码校验（默认拒绝，显式放行）。"""
from rest_framework.permissions import BasePermission

from apps.accounts.services import user_has_perm


class HasPerm(BasePermission):
    """校验权限码。usage: permission_classes = [HasPerm("attendance:record:export")]"""

    message = "无权限执行该操作"

    def __init__(self, *codes: str):
        self.codes = codes

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return all(user_has_perm(user, code) for code in self.codes)


class HasAnyPerm(BasePermission):
    """任一权限码命中即可。"""

    message = "无权限执行该操作"

    def __init__(self, *codes: str):
        self.codes = codes

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return any(user_has_perm(user, code) for code in self.codes)
