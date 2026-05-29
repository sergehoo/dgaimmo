"""Settings de développement local MutuelleX.

Utilisé quand DJANGO_ENV=dev (défaut) ou DJANGO_DEBUG=1.

Choix par défaut :
- DEBUG=True
- Hosts permissifs (localhost, 127.0.0.1, *.local)
- Emails console (aucun envoi réseau)
- HTTPS / HSTS / cookies sécurisés DÉSACTIVÉS
- Throttling relâché
- DRF browsable API activée
"""

from .base import *  # noqa: F401,F403
from .base import (
    BASE_DIR,
    REST_FRAMEWORK,
    env_bool,
    env_list,
    os,
)

DEBUG = True
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
# Hosts : on accepte les requêtes locales communes même sans config explicite
_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
DEFAULT_DEV_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "[::1]", "*.localhost"]
ALLOWED_HOSTS = sorted(set(_HOSTS + DEFAULT_DEV_HOSTS))

# CSRF / CORS en dev
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") or [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
]
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", True)

# Sécurité relâchée en dev — JAMAIS en prod
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
USE_X_FORWARDED_HOST = False

# Emails : console (visible dans la sortie runserver)
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

# Throttling relâché pour faciliter les tests
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"user": "1000/min", "anon": "200/min"}

# Activer la Browsable API en dev
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

# Logging verbeux en dev
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "dev": {
            "format": "[{asctime}] {levelname:7} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "dev"},
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",  # passer à DEBUG pour voir toutes les requêtes SQL
        },
        "mutuellex": {"handlers": ["console"], "level": "DEBUG"},
    },
}

# Astuce dev : afficher la barre de progression des migrations
SHELL_PLUS_PRINT_SQL = env_bool("SHELL_PLUS_PRINT_SQL", False)

# Bandeau visuel pour ne pas confondre avec la prod
INTERNAL_IPS = ["127.0.0.1", "::1"]


# GDAL / GEOS — surchargeable par variable d'environnement
GDAL_LIBRARY_PATH = os.getenv('GDAL_LIBRARY_PATH', '/opt/homebrew/opt/gdal/lib/libgdal.dylib')
GEOS_LIBRARY_PATH = os.getenv('GEOS_LIBRARY_PATH', '/opt/homebrew/opt/geos/lib/libgeos_c.dylib')
