import os
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# 确保日志目录存在
_LOG_DIR = BASE_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-change-me")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
SITE_TITLE = os.getenv("SITE_TITLE", "未配置标题")
ALLOWED_HOSTS = [
    "*",  # 允许所有主机访问，生产环境请替换为具体域名或IP
    # h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "web",
    "api",
]

APPEND_SLASH = False

MIDDLEWARE = [
    "web.middleware.StripTrailingSlashMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "web.middleware.LoginRequiredMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "mysql.connector.django",
        "NAME": os.getenv("MYSQL_DATABASE", "power_bank"),
        "USER": os.getenv("MYSQL_USER", "root"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", "password"),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "CONN_MAX_AGE": 600,  # 持久连接 10 分钟，避免每请求新建 TCP 连接
        "OPTIONS": {
            "charset": "utf8mb4",
            "collation": "utf8mb4_general_ci",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF pagination config for user list API
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.auth.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": SITE_TITLE,
    "DESCRIPTION": f"{SITE_TITLE} API 文档",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
    },
    "SCHEMA_PATH_PREFIX": r"/api",
    "TAGS": [
        {"name": "token", "description": "JWT Token 接口"},
        {"name": "users", "description": "用户管理接口"},
        {"name": "merchants", "description": "商户管理接口"},
        # {"name": "orders", "description": "订单管理接口"},
        # {"name": "profits", "description": "分润管理接口"},
        {"name": "invite-codes", "description": "邀请码管理接口"},
        {"name": "profile", "description": "个人资料接口"},
        {"name": "wallet", "description": "钱包管理接口"},
        {"name": "withdraws", "description": "提现管理接口"},
        # {"name": "health", "description": "系统健康检查接口"},
        # {"name": "items", "description": "示例数据接口"},
    ],
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "debug_only": {
            "()": "config.logging_filters.LevelFilter",
            "level": logging.DEBUG,
        },
        "info_only": {
            "()": "config.logging_filters.LevelFilter",
            "level": logging.INFO,
        },
        "warning_only": {
            "()": "config.logging_filters.LevelFilter",
            "level": logging.WARNING,
        },
        "error_only": {
            "()": "config.logging_filters.LevelFilter",
            "level": logging.ERROR,
        },
    },
    "formatters": {
        "verbose": {
            "format": "{name} {levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "debug_file": {
            "class": "config.logging_filters.DatedFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "debug.log"),
            "when": "midnight",
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["debug_only"],
        },
        "info_file": {
            "class": "config.logging_filters.DatedFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "info.log"),
            "when": "midnight",
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["info_only"],
        },
        "warning_file": {
            "class": "config.logging_filters.DatedFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "warning.log"),
            "when": "midnight",
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["warning_only"],
        },
        "error_file": {
            "class": "config.logging_filters.DatedFileHandler",
            "filename": os.path.join(BASE_DIR, "logs", "error.log"),
            "when": "midnight",
            "backupCount": 30,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["error_only"],
        },
    },
    "loggers": {
        "django": {
            "handlers": ["debug_file", "info_file", "warning_file", "error_file"],
            "level": "WARNING",
            "propagate": True,
        },
        "api": {
            "handlers": ["debug_file", "info_file", "warning_file", "error_file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "web": {
            "handlers": ["debug_file", "info_file", "warning_file", "error_file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "": {
            "handlers": ["debug_file", "info_file", "warning_file", "error_file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_HEADERS = ('*')

CORS = [
    f"https://{h}"
    for h in ALLOWED_HOSTS
    if h and h != "localhost" and not h.startswith("127.")
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "https://localhost:5173",
    *CORS,
]

