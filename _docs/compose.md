# Local persistent Docker Compose (#59)

The existing single application image serves real React static assets and FastAPI under `/api`; PostgreSQL is a separate service. This is local container orchestration, not a hosted deployment, high-availability certification, live-mail proof or full-feature Playwright completion. [Actual SQLite data migration](storage-migration.md) is an explicit separate operation and is never run by Compose startup.

## Prerequisites and private configuration

Install Docker Engine/Desktop with Linux containers and the Docker Compose V2 plugin. A working Docker daemon, image-registry access and a free loopback HTTP port are required. This workspace has no local Docker/WSL/Podman; actual verification uses the public repository's standard Ubuntu GitHub runner, not an OS installation or paid cloud service.

Copy `.env.compose.example` to a **new ignored** `.env.compose` only after checking the destination does not exist. Edit it privately; never publish it or paste secrets into chat, command history, CI logs or a `docker compose config` dump. Required values are POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, DATABASE_URL, JWT_SECRET_KEY and FRONTEND_ORIGINS. The example contains no working passwords or JWT key. Use random private secrets; JWT_SECRET_KEY must meet the application's existing non-placeholder minimum32-character rule. Keep it stable across restarts or existing sessions/codes will fail.

DATABASE_URL must explicitly select PostgreSQL and match the database, role and password configured for `db`, with hostname **db**, port5432 and dialect `postgresql+psycopg`. Percent-encode username/password/database URL components when needed (`urllib.parse.quote(value, safe='')`); do not percent-encode the whole URL. PostgreSQL password itself remains the original unencoded value. Use a private editor or secret manager to assemble this configuration rather than putting credentials into CLI arguments. Secrets are runtime environment only, never Docker build arguments/layers. Docker administrators can inspect container environment: local Docker access is privileged. Do not dump it into public artifacts.

For local HTTP keep APP_ENV=development, REFRESH_COOKIE_SECURE=false and FRONTEND_ORIGINS exactly matching the browser origin, e.g. `["http://127.0.0.1:8000"]`. APP_PORT8000 is published **only on127.0.0.1**. Change both port/origin if another local app uses it. The database has no published host port. Production mode retains existing HTTPS-origin/Secure-cookie validation; this package does not silently disable it or provide TLS termination. Changing an existing PostgreSQL volume's POSTGRES_PASSWORD environment does not automatically change database role credentials: use separately reviewed administration, not volume deletion.

Optional SMTP_HOST/PORT/USERNAME/PASSWORD/FROM_EMAIL/SECURITY are passed only when configured. Base Compose contains no mail catcher, code endpoint, test account, default application administrator or mail bypass. Missing SMTP remains the existing application's safe delivery failure; do not claim real inbox delivery from these container checks. Full controlled-mail E2E belongs to #60.

## Build/start and inspect

From repository root, after private configuration:

```powershell
docker compose --env-file .env.compose up --build --detach
docker compose --env-file .env.compose ps --all
```

Open http://127.0.0.1:8000 (or your selected APP_PORT). The official PostgreSQL18.6 image is pinned by digest. Its project-scoped `pgdata` named volume mounts **/var/lib/postgresql**, with PostgreSQL18's version-specific data directory below it; do not replace it with the legacy `/var/lib/postgresql/data` mount. The project-scoped `uploads` named volume mounts `/data/uploads`. No user host database/uploads directory or arbitrary external volume is mounted.

Startup waits for PostgreSQL health, a successful bounded one-shot Alembic upgrade, and upload-volume initialization before serving the app. The migration helper captures driver output and prints a generic failure, with a60s subprocess limit; it never downgrades, resets schema or imports data. Only legitimate fixed-category schema migrations run. The root upload initializer changes owner/mode of the exact declared volume root once; it accepts no caller path and never recursively changes ownership. The app retains image UID/GID10001 and writes private image namespaces inside that volume. App filesystem is otherwise read-only, with a small ephemeral `/tmp`.

Check migration completion with the service status (exit0) rather than treating a running DB as successful migration. If it fails, stop the app, check private configuration/database/migration compatibility and preserve the volumes; do not reset data to make it pass. A deliberately failed fresh migration must keep the app unstarted.

```powershell
curl.exe --fail http://127.0.0.1:8000/health/live
curl.exe --fail http://127.0.0.1:8000/health/ready
```

GET/HEAD `/health/live` returns minimal process liveness. `/health/ready` returns200 only when its required PostgreSQL is reachable and reports the published `0003_listings` head; otherwise it returns sanitized503. Responses are JSON status only with no-store, no credentials/paths/stack traces. The probe uses a separate read-only connection,2s connect and1s query timeout, at most two worker slots off the event loop and a4s response deadline. It does not wait on the business engine's30s pool-acquisition timeout. Saturation fails ready closed without scheduling unbounded work. This readiness contract is PostgreSQL-specific; the existing standalone SQLite entry point still works, but its new PostgreSQL readiness endpoint returns503. Standalone canonical OpenAPI/business guards remain unchanged.

Compose `depends_on` gates **startup**, not continuous dependent shutdown. Stopping PostgreSQL makes readiness unhealthy while liveness can still respond; restarting it allows readiness and existing pool reconnect behavior to recover. Compose does not restart every dependent automatically or certify application recovery for arbitrary outages.

## Retain data across stop/replacement

Use the same project name and private configuration:

```powershell
docker compose --env-file .env.compose stop
docker compose --env-file .env.compose up --detach
docker compose --env-file .env.compose up --detach --force-recreate db app
docker compose --env-file .env.compose down
docker compose --env-file .env.compose up --detach
```

These commands preserve named volumes. Keep the JWT/origin/cookie configuration stable so retained session data can still authorize users. Renaming the Compose project selects different named volumes; an empty new project is not proof of lost data. Schema upgrades should follow a reviewed backup/maintenance plan; major PostgreSQL upgrades need an explicit data upgrade/migration, not just editing the image tag.

**Destructive disposable-project cleanup only:** confirm the selected project is your throwaway verification project, not a real installation, before running `docker compose --project-name YOUR_DISPOSABLE_PROJECT --env-file .env.compose down --volumes --remove-orphans`. This deletes that project's database and uploaded images. No global Docker prune or unrelated container/volume deletion is part of this package. Retain real-data backups independently; production backup/restore/resource operations belong to #90.

## Reproduce the isolated real-engine verification

`python -m tools.compose_smoke` builds the actual image and creates uniquely named owned projects, generated runtime secrets and fresh project volumes. It explicitly uses an empty env-file and never reads a user's `.env.compose`. Supply CONTAINER_PLAYWRIGHT_MODULE pointing to installed pinned Playwright1.62.1 and CONTAINER_BROWSER if Chrome is not at the documented runner path. The harness exercises actual connected React/API and PostgreSQL; no browser API mocks or external email are used. Fixture-only creation/publication stays in the harness, not startup or application services.

Checks include required-secret refusal, fresh zero-user/category-only startup, non-root mounted private uploads, migration-head readiness, DB outage/recovery, account/session/private-avatar/listing-image persistence across replacement and down/up, and a separate fresh project whose failed migration prevents app start. The verifier removes only its generated project-labelled containers, volumes, networks and unique image, checks success/failure cleanup and emits sanitized JSON plus desktop/mobile screenshots. The narrow `compose-verification.yml` workflow uses a standard public Ubuntu runner, read-only permissions and no secrets, deployment or registry publication. Full CI/CD remains #86/#87 and feature E2E remains #60 onward.

Backend checks are `python -m unittest discover -s tests -v` with the existing guarded disposable PostgreSQL prerequisites, and `python -m tools.export_openapi --check`. A container result requires actual Docker execution and independent QA on the exact candidate; syntax/YAML/mock-only tests cannot substitute for it.
