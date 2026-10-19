"""字段级动态脱敏。

数据库存明文，序列化出口统一脱敏；查看明文需走二次授权（申请 + 审批 + 时限），且每次查看留痕。
"""
import hashlib
import logging
import re

from django.conf import settings
from django.utils import timezone

from apps.common.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

MASK_RULES = {
    "mobile": lambda v: v[:3] + "****" + v[-4:] if v and len(v) >= 7 else "***",
    "id_card": lambda v: v[:6] + "********" + v[-4:] if v and len(v) >= 15 else "***",
    "bank_card": lambda v: v[:4] + " **** **** " + v[-4:] if v and len(v) >= 8 else "***",
    "email": lambda v: (v[:2] + "***" + v[v.find("@"):]) if v and "@" in v else "***",
    "salary": lambda v: "***",
    "name": lambda v: (v[0] + "*" * (len(v) - 1)) if v else "***",
}

DEFAULT_MASK = lambda v: "***"  # noqa: E731


def mask_value(field: str, value):
    """按字段名脱敏。未知字段一律返回 ***。"""
    if value in (None, ""):
        return value
    value = str(value)
    return MASK_RULES.get(field, DEFAULT_MASK)(value)


def grant_key(user_id: int, field: str, obj_type: str, obj_id) -> str:
    return f"sens:grant:{obj_type}:{obj_id}:{field}:u{user_id}"


def grant_plaintext(user_id: int, field: str, obj_type: str, obj_id, minutes: int | None = None) -> int:
    """授予限时明文查看权，返回有效期秒数。"""
    minutes = minutes or settings.SECURITY["SENSITIVE_GRANT_MINUTES"]
    cache_set(grant_key(user_id, field, obj_type, obj_id), timezone.now().isoformat(), minutes * 60)
    return minutes * 60


def has_grant(user_id: int, field: str, obj_type: str, obj_id) -> bool:
    return cache_get(grant_key(user_id, field, obj_type, obj_id)) is not None


def revoke_grant(user_id: int, field: str, obj_type: str, obj_id) -> None:
    from apps.common.cache import cache_delete

    cache_delete(grant_key(user_id, field, obj_type, obj_id))


def should_mask(user, field: str) -> bool:
    """判断是否应对该用户脱敏。超管与 HR 角色可见明文。"""
    if field not in settings.SENSITIVE_FIELDS:
        return False
    if user is None or not getattr(user, "is_authenticated", False):
        return True
    if getattr(user, "is_superuser", False):
        return False
    try:
        from apps.accounts.services import user_has_perm

        return not user_has_perm(user, "sensitive:plaintext:view")
    except Exception:  # 权限服务异常时保守脱敏
        return True


def fingerprint(value: str) -> str:
    """用于校验与日志的单向指纹，避免日志落明文。"""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


PHONE_RE = re.compile(r"1[3-9]\d{9}")


def contains_sensitive(text: str) -> bool:
    if not text:
        return False
    return bool(PHONE_RE.search(text))
