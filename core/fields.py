"""Champs personnalisés MutuelleX.

`geo_point_field` permet un mode dual :
- ENABLE_GIS=1 → vraie colonne PostGIS `geography(Point)` (recommandé en prod).
- ENABLE_GIS=0 → JSONField simple (dev/SQLite, pas de carte interactive).

Important : on n'utilise jamais `default=dict` côté JSONField pour éviter
d'envoyer un `{}::jsonb` dans une colonne `geography` lorsque la base a été
créée avec PostGIS mais que le process Django tourne sans `ENABLE_GIS=1`.
Avec `default=None` + `null=True`, l'INSERT envoie `NULL` qui est accepté
par les deux types de colonnes.
"""

import os

from django.db import models


def _gis_enabled() -> bool:
    return os.getenv("ENABLE_GIS", "0").lower() in {"1", "true", "yes", "on"}


def geo_point_field(**kwargs):
    """Retourne un champ géographique (PostGIS) ou JSON selon ENABLE_GIS."""
    if _gis_enabled():
        from django.contrib.gis.db.models import PointField

        # null=True par défaut côté PostGIS aussi pour rester cohérent
        kwargs.setdefault("null", True)
        kwargs.setdefault("blank", True)
        return PointField(geography=True, **kwargs)

    # Fallback JSON : pas de default=dict pour éviter `{}` -> geography
    kwargs.setdefault("null", True)
    kwargs.setdefault("blank", True)
    kwargs.setdefault("default", None)
    return models.JSONField(**kwargs)
