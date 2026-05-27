import os

from django.db import models


def geo_point_field(**kwargs):
    if os.getenv("ENABLE_GIS", "0") == "1":
        from django.contrib.gis.db.models import PointField

        return PointField(geography=True, **kwargs)
    return models.JSONField(default=dict, blank=True, **kwargs)
