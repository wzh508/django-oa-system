"""RBAC 内省：扫描所有视图集，收集强制权限码与 perm_prefix。

供 init_base（权限点登记/角色授权）与 verify_security（越权自检矩阵）复用，
保证「接口强制的权限码」与「登记的权限点」完全一致。
"""
from django.apps import apps as django_apps

from apps.accounts.management.commands.init_base import PERMISSIONS, ROLE_PERMS

STANDARD_ACTIONS = ["list", "create", "retrieve", "update", "partial_update", "destroy"]
VIEWSET_MODULE_SUFFIX = ".views"

# 视图集基类（用于 isinstance 判断）
def _base_classes():
    from apps.common.viewsets import BaseModelViewSet, BaseViewSet
    from rest_framework.viewsets import GenericViewSet, ModelViewSet, ViewSet

    return (BaseViewSet, BaseModelViewSet, GenericViewSet, ViewSet, ModelViewSet)


def _iter_viewset_classes():
    bases = _base_classes()
    seen = set()
    for app_config in django_apps.get_app_configs():
        mod_path = f"{app_config.name}{VIEWSET_MODULE_SUFFIX}"
        try:
            module = __import__(mod_path, fromlist=["*"])
        except Exception:
            continue
        for attr in dir(module):
            obj = getattr(module, attr, None)
            if (isinstance(obj, type) and issubclass(obj, bases) and obj not in bases
                    and not attr.startswith("__")):
                if obj in seen:
                    continue
                seen.add(obj)
                yield obj


def collect_enforced_codes():
    """返回所有视图集实际强制的权限码集合。"""
    enforced = set()
    for cls in _iter_viewset_classes():
        prefix = getattr(cls, "perm_prefix", "") or ""
        perm_map = getattr(cls, "perm_map", {}) or {}
        open_actions = getattr(cls, "open_actions", set()) or set()
        actions = list(STANDARD_ACTIONS)
        for name in dir(cls):
            method = getattr(cls, name, None)
            if callable(method) and getattr(method, "url_path", None) is not None:
                actions.append(name)
        for action in set(actions):
            if action in perm_map:
                code = perm_map[action]
            elif action in open_actions:
                code = None
            elif prefix:
                code = f"{prefix}:{action}"
            else:
                code = None
            if code:
                enforced.add(code)
    return enforced


def collect_perm_prefixes():
    """返回所有视图集使用的 perm_prefix 集合（如 announcement / workflow:task / accounts:user）。"""
    prefixes = set()
    for cls in _iter_viewset_classes():
        prefix = getattr(cls, "perm_prefix", "") or ""
        if prefix:
            prefixes.add(prefix)
    return prefixes


def registered_codes():
    return {code for _, code, _, _ in PERMISSIONS}


def referenced_codes():
    """菜单与角色中引用、但未登记的权限码。"""
    refs = set()

    def walk(nodes):
        for node in nodes:
            _, _, _, _, _, _, perm, children = node
            if perm:
                refs.add(perm)
            walk(children)

    walk(__import__("apps.accounts.management.commands.init_base", fromlist=["MENUS"]).MENUS)
    for codes in ROLE_PERMS.values():
        for c in codes:
            if c != "*":
                refs.add(c)
    return refs


__all__ = [
    "STANDARD_ACTIONS", "collect_enforced_codes", "collect_perm_prefixes",
    "registered_codes", "referenced_codes",
]
