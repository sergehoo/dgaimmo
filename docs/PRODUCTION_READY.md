# DGA-IMO360 Production Readiness

## Go-live gates

- `DJANGO_DEBUG=0`.
- `DJANGO_SECRET_KEY` unique, secret, 50 characters minimum.
- `DJANGO_ALLOWED_HOSTS` contains only explicit production domains.
- `CSRF_TRUSTED_ORIGINS` contains the HTTPS frontend/admin origins.
- PostgreSQL/PostGIS and Redis are externalized or backed by persistent volumes.
- HTTPS is terminated by Traefik with LetsEncrypt.
- `/healthz/` responds for liveness.
- `/readyz/` validates database and cache readiness.
- `python manage.py check --deploy` passes before release.
- The test suite used in CI passes before release.

## Required environment

Use `.env.example` as the contract for production values. Replace every `change-me` value before deployment.

Critical variables:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `POSTGRES_PASSWORD`
- `LETSENCRYPT_EMAIL`
- `APP_DOMAIN`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

## Release flow

1. Build the image.
2. Run `python manage.py check --deploy`.
3. Run migrations: `python manage.py migrate --noinput`.
4. Collect static files: `python manage.py collectstatic --noinput`.
5. Start web, celery worker, celery beat, redis, postgres and Traefik.
6. Verify `/healthz/`, `/readyz/`, `/api/schema/` and `/console/`.
7. Create the first superuser or bootstrap tenant admin.

## Security baseline

- Secure cookies are enabled when `DJANGO_DEBUG=0`.
- HSTS is enabled by default when `DJANGO_DEBUG=0`.
- `SECURE_PROXY_SSL_HEADER` is configured for Traefik.
- API access uses JWT and tenant-aware permissions.
- Session cookies are HTTP-only and SameSite=Lax.
- Admin Django stays separate from the custom SaaS console.
- Security audit middleware records denied API requests.

## Operations

- Use Flower behind HTTPS and restrict it at network/proxy level.
- Monitor celery queues, Redis memory, PostgreSQL disk and web error rate.
- Schedule PostgreSQL backups at least daily.
- Test restoration into a separate environment monthly.
- Ship logs to a centralized collector before production traffic.
- Rotate `DJANGO_SECRET_KEY`, database passwords and provider API keys through a managed secret store.

## SaaS tenant controls

- Every business model must be linked to `mutuelle`.
- API requests must resolve the tenant from `X-Mutuelle-ID` or user default mutuelle.
- Superusers are the only actors allowed to cross tenant boundaries intentionally.
- Tenant quota updates must be audited before billing activation.

## Mobile Money and AI

- Mobile Money webhooks must be exposed only over HTTPS.
- Provider webhook secrets must not be committed.
- AI providers must be configured per environment.
- Cloud AI calls must be auditable and compatible with tenant quotas.
- Ollama remains the preferred local fallback for private/offline deployments.
