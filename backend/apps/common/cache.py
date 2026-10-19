"""缓存统一封装。

业务代码禁止直连 Redis，一律走本模块。
Redis 不可用时由 settings 自动降级为 LocMemCache / FileBasedCache，调用方无感知。
"""
import functools
import logging
from typing import Any, Callable

from django.core.cache import cache

logger = logging.getLogger(__name__)


def cache_get(key: str, default=None) -> Any:
    try:
        return cache.get(key, default)
    except Exception as exc:  # 缓存故障不得影响主流程
        logger.warning("cache get failed: %s", exc)
        return default


def cache_set(key: str, value: Any, timeout: int | None = 300) -> None:
    try:
        cache.set(key, value, timeout)
    except Exception as exc:
        logger.warning("cache set failed: %s", exc)


def cache_delete(key: str) -> None:
    try:
        cache.delete(key)
    except Exception as exc:
        logger.warning("cache delete failed: %s", exc)


def cache_delete_pattern(prefix: str) -> int:
    """删除指定前缀的键。Redis 用 keys 扫描，LocMem/File 退化为全量遍历。"""
    deleted = 0
    try:
        # Django 4.2 RedisCache：通过底层 redis-py 客户端扫描
        inner = getattr(cache, "_cache", None)
        get_client = getattr(inner, "get_client", None)
        if callable(get_client):
            client = get_client(write=True)
            for key in client.keys(f"{cache.key_prefix}:*:{prefix}*") or client.keys(f"*{prefix}*"):
                k = key.decode() if isinstance(key, bytes) else key
                cache.delete(k.removeprefix(cache.key_prefix + ":").split(":", 1)[-1])
                deleted += 1
            return deleted
        if hasattr(cache, "keys"):
            for key in cache.keys(f"{prefix}*"):  # type: ignore[attr-defined]
                cache.delete(key)
                deleted += 1
        elif hasattr(cache, "_cache"):  # LocMem
            for key in list(getattr(cache, "_cache", {}).keys()):
                if key.startswith(prefix):
                    cache.delete(key)
                    deleted += 1
    except Exception as exc:
        logger.warning("cache delete pattern failed: %s", exc)
    return deleted


# ------------------------------------------------------------------ 权限版本戳
def get_perm_version() -> int:
    """权限版本号。任何权限/角色/菜单变更后自增，使所有权限缓存自然失效。"""
    v = cache_get("perm:version", 1)
    return int(v) if v else 1


def bump_perm_version() -> int:
    v = get_perm_version() + 1
    cache_set("perm:version", v, timeout=60 * 60 * 24 * 30)
    return v


def perm_cache_key(user_id: int, kind: str) -> str:
    return f"perm:v{get_perm_version()}:u{user_id}:{kind}"


def cached(timeout: int = 300, key_func: Callable | None = None) -> Callable:
    """函数结果缓存装饰器，key 自动带上权限版本号。"""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if key_func is not None:
                suffix = key_func(*args, **kwargs)
            else:
                suffix = ":".join(str(a) for a in args if isinstance(a, (int, str)))
            key = f"fn:v{get_perm_version()}:{fn.__module__}.{fn.__name__}:{suffix}"
            hit = cache_get(key, "__MISS__")
            if hit != "__MISS__":
                return hit
            result = fn(*args, **kwargs)
            cache_set(key, result, timeout)
            return result

        return wrapper

    return decorator
