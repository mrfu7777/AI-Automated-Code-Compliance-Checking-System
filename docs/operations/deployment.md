# Pilot Deployment and Operations Manual

## Supported pilot topology

M7 is a single-organization release candidate for one licensed renovation project and one or two
architects. The supported topology is the existing Docker Compose stack: React, FastAPI, Celery,
PostgreSQL, Redis, and MinIO. The deterministic review path does not require an external model.

## Production configuration

1. Copy `.env.example` to `.env` and replace every `change-me` value.
2. Set `APP_ENV=production` and `AUTH_MODE=api_key`.
3. Generate independent high-entropy values for `BOOTSTRAP_API_KEY`, `API_KEY_PEPPER`, database
   credentials, and MinIO credentials. Never commit them.
4. Put the API and web app behind an HTTPS reverse proxy. Restrict PostgreSQL, Redis, and MinIO
   to the private deployment network.
5. Start with `docker compose -f infra/docker-compose.yml up --build --detach`.
6. Apply migrations with `docker compose -f infra/docker-compose.yml exec api alembic upgrade head`.
7. Verify `/api/v1/health`, `/api/v1/ready`, the web page, and a test upload/check/report flow.

Production startup fails when API-key authentication or non-placeholder secrets are missing.
Enter the bootstrap key in the web pilot-key field; it is kept only in browser session storage and
acts as the pilot administrator. Create named, expiring architect keys through
`POST /api/v1/access/api-keys`. Rotate the bootstrap secret under the deployment's secret-management
procedure if it is exposed; it is configuration, not a database key that the revoke endpoint can
remove.

## Daily operation

- Inspect `GET /api/v1/operations/overview` as an administrator for failed jobs, open findings,
  storage growth, feedback status, and external-model use/cost.
- Inspect `GET /api/v1/operations/audit-events` when investigating access or changes.
- Retry only failed jobs. The persisted worker guard prevents a completed job from executing twice.
- Treat unexpected false-compliant findings, missing evidence, or cross-tenant access as release
  blockers. Stop the pilot and preserve logs, request IDs, the review snapshot, and input hashes.
- Keep `EXTERNAL_MODEL_ENABLED=false` unless a reviewed adapter is added. Model unavailability does
  not disable verified facts or deterministic checks.

## Upgrade and rollback

Back up PostgreSQL and MinIO first. Deploy only tagged images/commits, run migrations once, then run
the smoke flow. Application rollback must remain compatible with the applied schema; restore the
pre-upgrade database and object-store backup together if a schema rollback is required.

## Shutdown

`docker compose -f infra/docker-compose.yml down` stops services without deleting named volumes.
Never add `--volumes` in a real pilot unless a verified, restorable backup exists and deletion is
explicitly intended.
