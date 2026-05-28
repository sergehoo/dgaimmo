"""Settings de production MutuelleX.

Utilisé quand DJANGO_ENV=prod ou DJANGO_DEBUG=0.

Hardening :
- DEBUG=False forcé
- Validation stricte du SECRET_KEY et ALLOWED_HOSTS
- HTTPS / HSTS / cookies sécurisés activés
- Throttling resserré
- Logging applicatif file + console
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import (
    BASE_DIR,
    env_bool,
    env_list,
    os,
)

DEBUG = False

# Validation du SECRET_KEY
_UNSAFE_KEYS = {
    "",
    "change-me",
    "dev-only-mutuellex-secret-key-change-me-32-plus",
    "change-this-production-secret-key-with-at-least-fifty-characters-dga-imo360",
}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if SECRET_KEY in _UNSAFE_KEYS or len(SECRET_KEY) < 50:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be a unique value of at least 50 characters in production."
    )

# Hosts obligatoires
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list explicit domains in production (no '*')."
    )

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS is required in production.")

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = False

# Sécurité HTTPS / HSTS
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 365)))  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", True)
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", True)
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")

# Email réel en prod (par défaut SMTP, configurable via .env)
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "MutuelleX <no-reply@mutuellex.com>")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Admins (alertes 5xx)
_admins_env = env_list("DJANGO_ADMINS")
ADMINS = [tuple(item.split(":", 1)) for item in _admins_env if ":" in item]
MANAGERS = ADMINS

# Cache Redis (utilise REDIS_URL hérité de base.py)
from .base import REDIS_URL  # noqa: E402

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("DJANGO_CACHE_URL", REDIS_URL),
        "TIMEOUT": 60,
    }
}

# Logging production : fichier rotatif + console
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "prod": {
            "format": "[{asctime}] {levelname:7} {name} pid={process:d}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "prod"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "mutuellex.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "prod",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "include_html": True,
        },
    },
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO"},
        "django.request": {
            "handlers": ["console", "file", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console", "file", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        "mutuellex": {"handlers": ["console", "file"], "level": "INFO"},
    },
}

# Throttling resserré en prod (déjà défini dans base, on rappelle pour clarté)
from .base import REST_FRAMEWORK  # noqa: E402

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"user": "120/min", "anon": "20/min"}
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = ("rest_framework.renderers.JSONRenderer",)
