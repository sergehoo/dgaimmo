"""Configuration commune MutuelleX (dev & prod).

Tout ce qui est partagé par les environnements vit ici. Les overrides
spécifiques sont dans ``dev.py`` et ``prod.py``.

Variables d'environnement importantes (extraites de ``.env``) :

- ``DJANGO_ENV``           ``dev`` (défaut) | ``prod``
- ``DJANGO_SECRET_KEY``    secret (50+ chars en prod)
- ``DJANGO_DEBUG``         ``0`` | ``1``
- ``DJANGO_ALLOWED_HOSTS`` liste séparée par virgules
- ``CSRF_TRUSTED_ORIGINS`` liste séparée par virgules
- ``ENABLE_GIS``           ``1`` pour activer PostGIS
- ``POSTGRES_*``           DB credentials
- ``REDIS_URL``            broker celery + channels
- ``USE_SQLITE``           ``1`` pour basculer en SQLite (dev)
"""

from pathlib import Path
import os
import warnings
from datetime import timedelta

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# settings/base.py → settings/ → config/ → BASE_DIR (racine projet)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Chargement automatique de .env (+ .env.local override)
# ---------------------------------------------------------------------------
# Indispensable pour que des variables comme ENABLE_GIS=1, POSTGRES_ENGINE,
# DJANGO_SECRET_KEY... soient visibles du process Django (runserver, gunicorn,
# manage.py). Sans cela on a des incohérences (ex. colonne PostGIS côté DB
# mais JSONField côté Python).
#
# Convention :
#   1. .env          → config "canonique" partagée (versionnée selon besoin),
#                      souvent calibrée pour Docker Compose (hôtes mutuellex-*).
#   2. .env.local    → overrides locaux (non versionné, par développeur),
#                      typiquement POSTGRES_HOST=localhost, REDIS_URL=redis://localhost,
#                      ENABLE_GIS=0... Charge APRÈS .env avec override=True.
try:
    from dotenv import load_dotenv

    _env_path = BASE_DIR / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

    _env_local_path = BASE_DIR / ".env.local"
    if _env_local_path.exists():
        load_dotenv(_env_local_path, override=True)
except ImportError:
    # python-dotenv non installé : on continue. Docker Compose injecte les vars.
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def env_bool(name, default=False):
    return os.getenv(name, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Auto-détection des bibliothèques GDAL / GEOS (PostGIS)
# ---------------------------------------------------------------------------
# Django GIS requiert deux libs natives (GDAL et GEOS) en plus de PostGIS.
# Sur macOS, Homebrew les installe dans /opt/homebrew (Apple Silicon) ou
# /usr/local (Intel). Sur Linux, elles sont en /usr/lib/x86_64-linux-gnu.
# Sans ces libs, Django lève "Could not find the GDAL library" au démarrage.
#
# Cette section cherche les libs si :
#   - ENABLE_GIS=1
#   - GDAL_LIBRARY_PATH / GEOS_LIBRARY_PATH ne sont pas déjà définis
# Si elles sont introuvables, on désactive automatiquement le GIS en dev
# pour ne pas bloquer le démarrage (mais on émet un warning).
def _autodetect_gis_libraries() -> tuple[bool, list[str]]:
    """Retourne (gis_ok, messages). Configure GDAL_LIBRARY_PATH / GEOS_LIBRARY_PATH."""
    import glob

    messages: list[str] = []

    candidates = {
        "gdal": [
            "/opt/homebrew/lib/libgdal.dylib",                  # macOS Apple Silicon
            "/opt/homebrew/opt/gdal/lib/libgdal.dylib",
            "/usr/local/lib/libgdal.dylib",                     # macOS Intel
            "/usr/local/opt/gdal/lib/libgdal.dylib",
            "/opt/local/lib/libgdal.dylib",                     # MacPorts
            "/usr/lib/x86_64-linux-gnu/libgdal.so",             # Debian/Ubuntu
            "/usr/lib/aarch64-linux-gnu/libgdal.so",
            "/usr/lib64/libgdal.so",                            # RHEL/Fedora
        ],
        "geos": [
            "/opt/homebrew/lib/libgeos_c.dylib",
            "/opt/homebrew/opt/geos/lib/libgeos_c.dylib",
            "/usr/local/lib/libgeos_c.dylib",
            "/usr/local/opt/geos/lib/libgeos_c.dylib",
            "/opt/local/lib/libgeos_c.dylib",
            "/usr/lib/x86_64-linux-gnu/libgeos_c.so",
            "/usr/lib/aarch64-linux-gnu/libgeos_c.so",
            "/usr/lib64/libgeos_c.so",
        ],
    }

    def _find(env_var, paths, label):
        if os.getenv(env_var):
            return os.getenv(env_var), True  # déjà défini → on respecte
        # Match exact d'abord
        for p in paths:
            if os.path.exists(p):
                return p, True
        # Sinon match avec versions (libgdal.36.dylib, libgeos_c.1.dylib...)
        for p in paths:
            base = p.replace(".dylib", "").replace(".so", "")
            for ext in (".dylib", ".so", ".so.*"):
                for hit in glob.glob(f"{base}*{ext}"):
                    return hit, True
        return None, False

    gdal_path, gdal_ok = _find("GDAL_LIBRARY_PATH", candidates["gdal"], "GDAL")
    geos_path, geos_ok = _find("GEOS_LIBRARY_PATH", candidates["geos"], "GEOS")

    if gdal_ok and gdal_path and not os.getenv("GDAL_LIBRARY_PATH"):
        os.environ["GDAL_LIBRARY_PATH"] = gdal_path
        messages.append(f"[MutuelleX] GDAL trouvée : {gdal_path}")
    if geos_ok and geos_path and not os.getenv("GEOS_LIBRARY_PATH"):
        os.environ["GEOS_LIBRARY_PATH"] = geos_path
        messages.append(f"[MutuelleX] GEOS trouvée : {geos_path}")

    if not (gdal_ok and geos_ok):
        missing = []
        if not gdal_ok:
            missing.append("GDAL")
        if not geos_ok:
            missing.append("GEOS")
        messages.append(
            "[MutuelleX] Bibliothèques GIS manquantes : %s. "
            "Installez-les avec :\n"
            "  • macOS (Homebrew)  : brew install gdal geos\n"
            "  • Ubuntu/Debian     : sudo apt install gdal-bin libgdal-dev libgeos-dev\n"
            "  • Fedora/RHEL       : sudo dnf install gdal gdal-devel geos geos-devel\n"
            "  • Docker            : ajoutez gdal-bin libgdal-dev dans le Dockerfile\n"
            "Ou désactivez GIS temporairement : ENABLE_GIS=0 (et USE_SQLITE=1 si la DB "
            "PostgreSQL contient déjà des colonnes 'geography')."
            % ", ".join(missing)
        )
        return False, messages

    return True, messages


_GIS_REQUESTED = env_bool("ENABLE_GIS")
_GIS_AUTODISABLED = False
_GIS_MESSAGES: list = []

if _GIS_REQUESTED:
    _gis_ok, _GIS_MESSAGES = _autodetect_gis_libraries()
    if not _gis_ok:
        # Soit on bloque (prod), soit on auto-désactive (dev) selon DJANGO_ENV.
        # En base on auto-désactive pour ne pas bloquer ; prod.py forcera plus tard si besoin.
        if env_bool("STRICT_GIS"):
            from django.core.exceptions import ImproperlyConfigured as _ImpErr

            raise _ImpErr(
                "STRICT_GIS=1 mais les bibliothèques GDAL/GEOS sont introuvables. "
                "Installez-les ou définissez ENABLE_GIS=0."
            )
        _GIS_AUTODISABLED = True
        os.environ["ENABLE_GIS"] = "0"
        # Si POSTGRES_ENGINE pointait vers postgis, on bascule sur le backend
        # PostgreSQL standard (sinon Django tentera de charger postgis qui
        # importe GDAL → boucle d'erreur).
        _orig_engine = os.environ.get("POSTGRES_ENGINE", "")
        if "postgis" in _orig_engine:
            os.environ["POSTGRES_ENGINE"] = "django.db.backends.postgresql"
            _GIS_MESSAGES.append(
                "[MutuelleX] POSTGRES_ENGINE basculé sur django.db.backends.postgresql "
                "(les colonnes 'geography' existantes resteront en base mais "
                "ne pourront pas être lues comme PointField)."
            )
        warnings.warn(
            "\n".join(_GIS_MESSAGES)
            + "\n[MutuelleX] GIS désactivé automatiquement pour ce process (fallback JSONField).",
            RuntimeWarning,
            stacklevel=1,
        )

if os.getenv("GDAL_LIBRARY_PATH"):
    GDAL_LIBRARY_PATH = os.getenv("GDAL_LIBRARY_PATH")
if os.getenv("GEOS_LIBRARY_PATH"):
    GEOS_LIBRARY_PATH = os.getenv("GEOS_LIBRARY_PATH")


# ---------------------------------------------------------------------------
# Sécurité de base — DEBUG et SECRET_KEY sont fixés dans dev.py / prod.py
# ---------------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

if env_bool("ENABLE_GIS"):
    DJANGO_APPS.append("django.contrib.gis")

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "channels",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
]

LOCAL_APPS = [
    "core",
    "accounts",
    "organizations",
    "mutuelles",
    "memberships",
    "contributions",
    "treasury",
    "accounting",
    "loans",
    "claims",
    "healthcare",
    "payments",
    "mobile_money",
    "notifications",
    "governance",
    "ai_engine",
    "analytics",
    "audit",
    "reports",
    "real_estate",
    "dashboard",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.ActiveTenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "core.middleware.SecurityAuditMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "builtins": ["django.contrib.humanize.templatetags.humanize"],
        },
    },
]


# ---------------------------------------------------------------------------
# Base de données + cohérence GIS
# ---------------------------------------------------------------------------
_ENABLE_GIS = env_bool("ENABLE_GIS")
_POSTGRES_ENGINE = os.getenv(
    "POSTGRES_ENGINE",
    "django.contrib.gis.db.backends.postgis" if _ENABLE_GIS else "django.db.backends.postgresql",
)

_engine_is_postgis = "postgis" in _POSTGRES_ENGINE
if _engine_is_postgis and not _ENABLE_GIS:
    warnings.warn(
        "[MutuelleX] Incohérence GIS : POSTGRES_ENGINE='%s' utilise PostGIS mais "
        "ENABLE_GIS n'est pas activé. Définissez ENABLE_GIS=1." % _POSTGRES_ENGINE,
        RuntimeWarning,
        stacklevel=1,
    )
elif _ENABLE_GIS and not _engine_is_postgis and "sqlite" not in _POSTGRES_ENGINE:
    warnings.warn(
        "[MutuelleX] ENABLE_GIS=1 mais POSTGRES_ENGINE='%s' n'est pas PostGIS. "
        "Les PointField ne seront pas opérationnels." % _POSTGRES_ENGINE,
        RuntimeWarning,
        stacklevel=1,
    )

DATABASES = {
    "default": {
        "ENGINE": _POSTGRES_ENGINE,
        "NAME": os.getenv("POSTGRES_DB", "mutuellex"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "weddingLIFE18"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

if env_bool("USE_SQLITE"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }


# ---------------------------------------------------------------------------
# Auth / DRF / JWT / OpenAPI
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard-home"
LOGOUT_REDIRECT_URL = "landing-page"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("core.permissions.IsTenantMember",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {"user": "120/min", "anon": "20/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MutuelleX API",
    "DESCRIPTION": "API SaaS multi-tenant pour mutuelles communautaires, microfinance et immobilier collectif.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}


# ---------------------------------------------------------------------------
# Channels / Celery / Redis
# ---------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)


# ---------------------------------------------------------------------------
# i18n / Statics / Médias
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = os.getenv("TIME_ZONE", "Africa/Abidjan")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")


# ---------------------------------------------------------------------------
# Sécurité (défauts communs — surchargés dans dev.py / prod.py)
# ---------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")
SECURE_REFERRER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))


# ---------------------------------------------------------------------------
# CSP
# ---------------------------------------------------------------------------
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdn.tailwindcss.com",
    "https://unpkg.com",
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com",      # FontAwesome
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdnjs.cloudflare.com",      # FontAwesome CSS
    "https://fonts.googleapis.com",      # éventuelles Google Fonts
)
CSP_FONT_SRC = (
    "'self'",
    "data:",
    "https://cdnjs.cloudflare.com",      # FontAwesome .woff2
    "https://fonts.gstatic.com",
)
CSP_IMG_SRC = ("'self'", "data:", "blob:", "https://images.unsplash.com")
CSP_CONNECT_SRC = ("'self'",)


# ---------------------------------------------------------------------------
# IA
# ---------------------------------------------------------------------------
AI_DEFAULT_PROVIDER = os.getenv("AI_DEFAULT_PROVIDER", "ollama")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")


# ---------------------------------------------------------------------------
# Logging par défaut (peut être surchargé en dev/prod)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "mutuellex": {"handlers": ["console"], "level": "INFO"},
    },
}
