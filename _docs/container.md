# Single packaged image (#57)

This package builds the existing real React frontend and FastAPI services into one image. It is local container packaging, not a cloud deployment or Compose/CI platform. **Candidate status: local checks passed; actual Docker image verification awaits the isolated `issue-57-container` hosted-runner workflow and independent QA.** Docker Desktop/CLI, WSL and Podman are absent on the development machine; no image run is claimed from local Python tests.

## Build and explicit initialization

From the repository root with a working Linux Docker engine:

```sh
docker build -t student-marketplace:local .
docker volume create marketplace-local-data
# For a NEW empty named volume only; never chown an unrelated host directory.
docker run --rm --user 0:0 -v marketplace-local-data:/data student-marketplace:local chown 10001:10001 /data
```

Configure the following variables in your shell or a private, access-restricted runtime env file **outside the build context**. Generate a fresh JWT secret with a password manager or `python -c "import secrets; print(secrets.token_urlsafe(48))"`; never commit it. The demonstration uses HTTP loopback and test mode; production requires HTTPS origins and `REFRESH_COOKIE_SECURE=true` under existing settings validation.

```text
APP_ENV=test
DATABASE_URL=sqlite+pysqlite:////data/marketplace.sqlite3
UPLOAD_DIR=/data/uploads
FRONTEND_ORIGINS=["http://127.0.0.1:8080"]
JWT_SECRET_KEY=<generated private secret, at least 32 characters>
```

`--env-file /private/path/runtime.env` below is an operator-supplied runtime file, not shipped with the image. Configure actual SMTP_HOST/PORT/USERNAME/PASSWORD/FROM_EMAIL/SECURITY when email delivery is wanted; missing SMTP does not produce fake success or expose codes. Verification never sends real external email. Keep the same JWT key and volume when restarting. Separate PostgreSQL remains supported via an explicit URL and `alembic.ini`; database/service orchestration is #59.

```sh
# Explicit one-off migration; normal startup NEVER auto-resets/migrates/seeds users.
docker run --rm --env-file /private/path/runtime.env -v marketplace-local-data:/data student-marketplace:local python -m alembic -c alembic-sqlite.ini upgrade head
docker run -d --name marketplace-local --env-file /private/path/runtime.env -v marketplace-local-data:/data -p 127.0.0.1:8080:8000 student-marketplace:local
docker inspect marketplace-local --format '{{.Config.User}}'
docker stop --time 15 marketplace-local
docker start marketplace-local
# When finished: remove only this container; retain the volume for your data.
docker stop --time 15 marketplace-local
docker rm marketplace-local
```

The image uses uid/gid10001, writable `/data`, exec-form Uvicorn signal handling, no proxy-header trust/access log and no Vite. `/` and known frontend routes (including `/listings/1`) serve the real SPA; `/assets` serves only built assets, never uploaded files. All backend routes are under `/api` (`/api/docs`, `/api/openapi.json`, `/api/auth/me`, protected binary routes). Unknown `/api` paths retain JSON404. The adapter strips the prefix before existing security/size/rate/authorization middleware and translates refresh cookie Path to `/api/auth`; same-origin credentials/CSRF/Origin/Bearer guards remain mandatory.

The container build sets `VITE_API_PREFIX=/api`. It accepts only a single-rooted path of ASCII segments, not URLs, dot segments, query, fragment, percent escapes or trailing slash. Existing separate-port development retains VITE_API_ORIGIN and its validated localhost fallback when no prefix is set. API DTO photo paths stay canonical; the shared request helper prefixes them exactly once. Existing development factories/API contracts are unchanged.

## Inputs, exclusions and verification

Dockerfile pins official multi-platform image digests: Node24.19.0 bookworm-slim (`a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df`) with npm12.2.0; Python3.13.15 slim-bookworm (`2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26`). Digests were read from Docker Hub's authenticated public manifest API on2026-11-02. npm uses package-lock.json; Python uses requirements.lock. No dependency changes were needed. OS package contents are bound by image digests; this is not a universal cross-architecture bit-for-bit build claim.

The default-deny `.dockerignore` admits only build/runtime inputs. It excludes private environments/git/data/uploads/caches/tests/evidence/node_modules and original mock code/photos. Two inert build-stage placeholders satisfy static import resolution; final production tree shaking excludes them. The final stage contains only Python dependencies, backend, the two existing migration streams/configs and real static output; no frontend source, Node, development fixtures or browser/test tools. Secrets are provided at execution, never ARG/COPY/baked ENV. Host ports bind loopback explicitly.

Local candidate checks on2026-11-02:294 backend tests passed, zero skips, in104.180s against guarded real PostgreSQL plus memory/file SQLite;166 frontend tests passed, typecheck, packaged real build/bundle isolation and deterministic standalone OpenAPI drift passed. The2 new backend tests exercise real packaged routing/session behavior;9 new frontend cases exercise prefix safety/binary auth headers. Local Node was24.22.1 (image pins24.19.0), Python3.13.15; these are local checks, not an unobserved image run. Existing historical counts/artifacts are not rewritten.

For actual engine verification, run `python3 tools/container_smoke.py` on a Docker-enabled machine. Optional browser proof requires Playwright1.62.1 and CONTAINER_PLAYWRIGHT_MODULE pointing to its module directory; CONTAINER_BROWSER selects a Chromium-compatible executable (default `/usr/bin/google-chrome`). The isolated workflow installs that exact driver in runner temp and runs actual browser sign-in/reload/detail navigation. It runs on standard ubuntu-24.04, read-only repository permission, no secrets, registry writes or deployment. Push trigger is restricted to `issue-57-container`; workflow_dispatch becomes usable after eventual default-branch publication. Root pushes only a preliminarily reviewed candidate to that branch, main remains unchanged until runtime QA PASS.

The smoke creates random owned image/container/volume names, migrations, ephemeral secrets and a synthetic verified account solely inside disposable test data. No public role/code bypass is added. It checks static/SPA MIME, real protected API/private-image denial/JSON404, nonroot identity, runtime file/layer/bundle exclusion, actual private image upload and authenticated read, graceful zero-exit stop and mounted account/session/photo retention across restart. It always removes its own container/volume/image. Secret-free `container-verification.json` binds actual GitHub SHA, image id, engine/Python/SQLite/Uvicorn/browser versions, completed checks and cleanup; browser screenshots contain no passwords/tokens. Inspect/download the exact workflow artifact and independently reproduce before claiming image PASS. Build cache may remain on the disposable runner; no unrelated Docker objects are pruned.
