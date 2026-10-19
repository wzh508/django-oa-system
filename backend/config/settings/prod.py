"""生产环境配置。"""
from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = [h.strip() for h in env_str("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]  # noqa: F405

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
