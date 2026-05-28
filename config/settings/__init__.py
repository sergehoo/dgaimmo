"""Point d'entrée du package config.settings.

Sélectionne automatiquement la configuration d'environnement.

Ordre de résolution :
1. ``DJANGO_ENV`` (recommandé) : valeurs ``prod``, ``production``, ``dev``,
   ``development``, ``local``, ``staging``.
2. ``DJANGO_DEBUG`` : ``1`` → dev, ``0`` → prod (legacy).
3. Défaut : ``dev`` (le moins risqué en cas d'oubli en local).

On charge ``.env`` ici en premier pour que ``DJANGO_ENV`` soit lisible
avant la sélection du module.
"""

import os
from pathlib import Path

# Chargement précoce de .env (+ .env.local override) pour que DJANGO_ENV soit visible
try:
    from dotenv import load_dotenv

    _BASE_DIR = Path(__file__).resolve().parent.parent.parent
    _env_path = _BASE_DIR / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
    _env_local_path = _BASE_DIR / ".env.local"
    if _env_local_path.exists():
        load_dotenv(_env_local_path, override=True)
except ImportError:
    pass


def _resolve_env() -> str:
    env = (os.getenv("DJANGO_ENV") or "").strip().lower()
    if env in {"prod", "production"}:
        return "prod"
    if env in {"dev", "development", "local", "staging"}:
        return "dev"
    # Fallback legacy : DJANGO_DEBUG
    debug = (os.getenv("DJANGO_DEBUG") or "").strip().lower()
    if debug in {"0", "false", "no", "off"}:
        return "prod"
    return "dev"


_ENV = _resolve_env()

if _ENV == "prod":
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
