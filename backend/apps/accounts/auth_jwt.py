"""JWT 增强：refresh 白名单 + 黑名单（Redis 不可用时自动降级为缓存）。"""
import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.cache import cache_delete, cache_get, cache_set

logger = logging.getLogger(__name__)

REFRESH_TTL = 7 * 24 * 3600
_BLACK_PREFIX = "jwt:black:"
_REFRESH_PREFIX = "jwt:refresh:"


def register_refresh(token: RefreshToken, user_id: int) -> None:
    jti = token.get("jti") or token.payload.get("jti")
    if jti:
        cache_set(f"{_REFRESH_PREFIX}{jti}", user_id, REFRESH_TTL)


def revoke_refresh(token_str: str) -> None:
    """登出：拉黑指定 refresh。"""
    try:
        token = RefreshToken(token_str)
        jti = token.get("jti")
        if jti:
            cache_delete(f"{_REFRESH_PREFIX}{jti}")
            cache_set(f"{_BLACK_PREFIX}{jti}", 1, REFRESH_TTL)
    except TokenError:
        return


def revoke_all_for_user(user_id: int) -> None:
    """强制下线：拉黑该用户所有 token（版本戳方式）。"""
    from apps.common.cache import bump_perm_version, cache_set

    cache_set(f"{_BLACK_PREFIX}user:{user_id}", bump_perm_version(), REFRESH_TTL)


def is_blacklisted(jti: str, user_id=None) -> bool:
    if jti and cache_get(f"{_BLACK_PREFIX}{jti}") is not None:
        return True
    if user_id is not None:
        stamp = cache_get(f"{_BLACK_PREFIX}user:{user_id}")
        if stamp is not None:
            from apps.common.cache import cache_get as _get

            # 登录签发时写入的 user version，早于黑名单戳即失效
            issued = _get(f"{_REFRESH_PREFIX}uv:{user_id}")
            if issued is None or int(issued) < int(stamp):
                return True
    return False


def mark_user_version(user_id: int) -> None:
    from apps.common.cache import get_perm_version

    cache_set(f"{_REFRESH_PREFIX}uv:{user_id}", get_perm_version(), REFRESH_TTL)


class CachedJWTAuthentication(JWTAuthentication):
    """在标准校验之上追加黑名单检查。"""

    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        jti = token.get("jti")
        user_id = token.get("user_id")
        if is_blacklisted(jti, user_id):
            raise InvalidToken("凭证已失效")
        return token

try:  # drf-spectacular 可选：让 Swagger 显示 Bearer 认证入口
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class CachedJWTScheme(OpenApiAuthenticationExtension):
        target_class = "apps.accounts.auth_jwt.CachedJWTAuthentication"
        name = "bearerAuth"

        def get_security_definition(self, auto_schema):
            from drf_spectacular.plumbing import build_bearer_security_scheme_object

            return build_bearer_security_scheme_object(
                header_name="Authorization", token_prefix="Bearer"
            )
except ImportError:  # pragma: no cover
    pass
