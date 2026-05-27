from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    return JsonResponse({"status": "ok", "service": "dga-imo360"})


def readyz(request):
    checks = {"database": False, "cache": False}
    status_code = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone()[0] == 1
    except Exception:
        status_code = 503

    try:
        cache.set("readyz", "ok", timeout=5)
        checks["cache"] = cache.get("readyz") == "ok"
    except Exception:
        status_code = 503

    if not all(checks.values()):
        status_code = 503
    return JsonResponse({"status": "ok" if status_code == 200 else "degraded", "checks": checks}, status=status_code)
