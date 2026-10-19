"""Django OA 基础配置。

所有环境差异项一律走环境变量，禁止在代码中硬编码密钥与地址。
环境变量说明见仓库根 .env.example。
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BASE_DIR.parent  # 仓库根

# 优先读取仓库根 .env，其次 backend/.env
for _p in (ROOT_DIR / ".env", BASE_DIR / ".env"):
    if _p.exists():
        load_dotenv(_p, override=False)
        break


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_str(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return default if v is None or v == "" else v


# ---------------------------------------------------------------- 安全
SECRET_KEY = env_str("DJANGO_SECRET_KEY", "django-insecure-dev-only-key-change-me-0123456789")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in env_str("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

# ---------------------------------------------------------------- 应用
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.messages",
]
THIRD_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
]
LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.workflow",
    "apps.attendance",
    "apps.announcement",
    "apps.document",
    "apps.hr",
    "apps.meeting",
    "apps.schedule",
    "apps.message",
    "apps.insight",
    "apps.lowcode",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.RequestLogMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- 数据库
# 只改 DB_ENGINE 即可在 MySQL / SQLite 之间切换，ORM 层不使用任何方言特有语法。
DB_ENGINE = env_str("DB_ENGINE", "mysql").lower()
if DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / env_str("DB_NAME", "oa_system.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env_str("DB_NAME", "oa_system"),
            "USER": env_str("DB_USER", "root"),
            "PASSWORD": env_str("DB_PASSWORD", ""),
            "HOST": env_str("DB_HOST", "127.0.0.1"),
            "PORT": env_str("DB_PORT", "3306"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            "TEST": {
                "CHARSET": "utf8mb4",
                "COLLATION": "utf8mb4_general_ci",
                "NAME": env_str("DB_TEST_NAME", "oa_test"),
            },
        }
    }

# ---------------------------------------------------------------- 缓存
# redis / locmem / file 三档，业务代码一律走 apps.common.cache，不得直连 Redis。
CACHE_BACKEND = env_str("CACHE_BACKEND", "redis").lower()
REDIS_URL = env_str("REDIS_URL", "redis://127.0.0.1:6379/1")
CACHE_TIMEOUT_DEFAULT = env_int("CACHE_TIMEOUT_DEFAULT", 300)
CACHE_VERSION_KEY = "perm:version"  # 权限版本戳，用于变更实时生效

if CACHE_BACKEND == "redis":
    try:
        import redis  # noqa: F401

        CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": REDIS_URL,
                "TIMEOUT": CACHE_TIMEOUT_DEFAULT,
                "KEY_PREFIX": "oa",
            }
        }
    except ImportError:
        CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "oa-fallback",
            }
        }
elif CACHE_BACKEND == "file":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(BASE_DIR / ".cache"),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "oa-default",
        }
    }

# ---------------------------------------------------------------- 异步任务
CELERY_BROKER_BACKEND = env_str("CELERY_BROKER_BACKEND", "redis").lower()  # redis|filesystem
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", "redis://127.0.0.1:6379/2")
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", "cache+memory://")
CELERY_FILESYSTEM_PATH = str(BASE_DIR / ".celery_broker")
CELERY_TIMEZONE = "Asia/Shanghai"

# ---------------------------------------------------------------- 认证
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
]

# ---------------------------------------------------------------- DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("apps.accounts.auth_jwt.CachedJWTAuthentication",),
    # 默认拒绝：未显式声明权限的接口一律不可访问
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("rest_framework.filters.SearchFilter", "rest_framework.filters.OrderingFilter"),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": env_int("DEFAULT_PAGE_SIZE", 20),
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "中小企业 OA 管理系统 API",
    "DESCRIPTION": "基于 Django + DRF 的中小企业办公自动化系统接口文档（OpenAPI 3）",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {},
}

# ---------------------------------------------------------------- 国际化 / 时区
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- 静态与媒体
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------- 文件安全
UPLOAD_MAX_SIZE = env_int("UPLOAD_MAX_SIZE", 20 * 1024 * 1024)
UPLOAD_ALLOWED_EXT = ["jpg", "jpeg", "png", "gif", "webp", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "zip"]

# ---------------------------------------------------------------- 安全策略
SECURITY = {
    # 连续失败 N 次锁定 M 分钟
    "LOGIN_FAIL_LIMIT": env_int("LOGIN_FAIL_LIMIT", 5),
    "LOGIN_LOCK_MINUTES": env_int("LOGIN_LOCK_MINUTES", 10),
    # 敏感字段二次授权有效期（分钟）
    "SENSITIVE_GRANT_MINUTES": env_int("SENSITIVE_GRANT_MINUTES", 30),
}
SENSITIVE_FIELDS = ["mobile", "id_card", "bank_card", "salary", "email"]

# ---------------------------------------------------------------- 分页上限
MAX_PAGE_SIZE = env_int("MAX_PAGE_SIZE", 100)

# ---------------------------------------------------------------- 日志
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "django.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "standard",
            "encoding": "utf-8",
        },
    },
    "root": {"handlers": ["console", "file"], "level": env_str("LOG_LEVEL", "INFO")},
}

CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", True)
CORS_ALLOWED_ORIGINS = [o.strip() for o in env_str("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env_str("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
