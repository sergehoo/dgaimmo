FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# --- Dépendances système (build + runtime) ---
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gdal-bin libgdal-dev \
        binutils libproj-dev \
        gettext curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --- Build-time : collectstatic ---
# Le .env présent dans le contexte est respecté par les settings, mais nous
# forçons ici un mode "build" pour que prod.py n'exige pas le vrai SECRET_KEY
# (un dummy suffit pour collectstatic). À l'exécution, on retombera sur les
# vraies variables d'environnement injectées par docker-compose / l'orchestrateur.
ENV DJANGO_BUILD_MODE=1 \
    DJANGO_SECRET_KEY=build-time-dummy-secret-key-NOT-USED-IN-RUNTIME-mutuellex-min50chars \
    DJANGO_ALLOWED_HOSTS=build.local \
    CSRF_TRUSTED_ORIGINS=https://build.local \
    ENABLE_GIS=0

RUN python manage.py collectstatic --noinput

# Nettoyage des variables build-time : à l'exécution, les vraies valeurs
# (DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, ENABLE_GIS, etc.) sont injectées
# par docker-compose env_file ou par l'orchestrateur (Kubernetes, Swarm).
ENV DJANGO_BUILD_MODE= \
    DJANGO_SECRET_KEY= \
    DJANGO_ALLOWED_HOSTS= \
    CSRF_TRUSTED_ORIGINS= \
    ENABLE_GIS=

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail http://127.0.0.1:8000/healthz/ || exit 1

CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "3"]
