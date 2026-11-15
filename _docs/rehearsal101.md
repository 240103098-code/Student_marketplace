# Disposable isolation and capacity rehearsal (#101)

Implementation candidate, **runtime acceptance pending**. Windows cannot run Docker here. No table in this document is a runtime PASS; the dedicated Linux run's sanitized `summary.json`, exact input/source hashes and independent QA are required. The existing Oracle demo and existing full CI/CD remain unchanged. This controller never uses SSH, Oracle settings, cloud secrets, a real dataset, the user's `.env`, the user's PostgreSQL on 55435, or real mail. Local success cannot establish hosted capacity or complete #102–#109.

## Invocation and execution route

Use a disposable Linux Docker/Compose machine with Python 3.13.15, the locked development requirements, Node 24.19.0, the existing locked `e2e` dependencies/Chromium, OpenSSL and `libnss3-tools` (`certutil`). These tools introduce no application dependency. Run from the checkout:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
npm ci --prefix e2e --ignore-scripts --no-audit --no-fund
export PLAYWRIGHT_BROWSERS_PATH=/absolute/disposable/browser-cache
node e2e/node_modules/@playwright/test/cli.js install --with-deps chromium
.venv/bin/python -m tools.rehearsal101 --confirm-disposable issue-101-synthetic-only
```

`rehearsal101-safe` must be empty or absent. Review/move its previous single safe report before another run; the controller does not delete caller evidence. The dedicated [workflow](../.github/workflows/rehearsal101.yml) runs automatically only on `issue-101-isolation-capacity`, or by deliberate dispatch. Root publishes the reviewed candidate branch; the engineer never pushes. No Oracle job is in this workflow. The unchanged existing CI also runs on branch push, but its Oracle job requires **main**. After actual rehearsal and independent QA, normal exact main publication still runs full existing CI and routine current Oracle CD. This does not activate the new topology on Oracle.

Controller work has a 27.5-minute deadline and separate bounded cleanup allowance, inside the job's 30-minute outer timeout. Every subprocess captures private output and has a finite timeout. Register/login/code/SMTP/config/native process outputs stay private. CI uploads only the constructed `rehearsal101-safe/summary.json`, retained seven days; it never uploads expanded Compose configuration, raw logs, inboxes, keys, browser profiles, tokens or private paths. No broad artifact glob or global Docker prune is used.

## Isolation and truthful TLS

Two fresh `marketplace101-<random>-dev/prod` projects own distinct PostgreSQL databases/roles/passwords, JWT and SMTP keys, PG/uploads volumes and internal networks. All resources carry both Compose ownership and a fresh explicit rehearsal owner label. No external/shared writable volume is accepted. The existing application Dockerfile/image, upload initializer, `backend.compose_runtime migrate` and completed-successfully startup dependencies are used. The standalone generated composition is opt-in and leaves default `compose.yaml` and all Oracle controllers unchanged. Actual mount/network membership, DB identities and secret inequality are checked without emitting secrets.

The origins are `https://dev.marketplace.test:<random>` and `https://prod.marketplace.test:<random>`. Different hostname scopes isolate cookies; ports alone do not. Dev runs `APP_ENV=development`; synthetic prod runs **APP_ENV=production**, HTTPS-only configured origins and Secure refresh cookies. A disposable Python standard-library TLS proxy in the existing image terminates HTTPS and forwards only to its own app. It does not trust forwarded headers. The backend is private HTTP inside that environment's internal Docker network, as with ordinary TLS termination; this is not end-to-end backend TLS. Only the TLS proxy publishes an app endpoint, bound to loopback.

One freshly generated one-day CA signs fixture web SANs and the `smtp` certificate. Python connects loopback while retaining `.test` SNI/Host and certificate validation. Chromium uses scoped host resolver rules and a temporary HOME's `.pki/nssdb`; only this NSS database trusts the CA. No global trust/hosts changes, `ignoreHTTPSErrors`, insecure Chromium flags, or certificate verification bypass is allowed. The browser must actually navigate/login over trusted TLS and observe normal host-only HttpOnly Secure `/api/auth` cookies in one shared browser context; the same source cookie must not appear in an actual request to the other host. The `/api/auth` cookie prefix is the existing packaged adapter's supported behavior.

Each fixture sends normal register/verification/login requests. Codes are consumed only from that stack's isolated authenticated STARTTLS sink, which has no external route; no identity/code/token is seeded in the database and no auth bypass exists. Own profile/avatar upload and read use supported HTTP routes. Anonymous profile/photo, other environment Bearer JWT, refresh cookie with correctly shaped normal CSRF, and wrong Origin are tested separately. Network denial first verifies the inspected prod DB IP is reachable from prod, then attempts that exact IP from dev. Wrong dev credentials are also tested from a process on the prod network so credential denial is independent of network denial.

Prod's synthetic data dump hash, Alembic head, private uploaded bytes hash and normal authenticated read/readiness are checked after each dev write, real downgrade/upgrade, invalid Alembic revision startup failure, exact-owned dev reset, invalid JWT startup failure and valid JWT replacement. Both failures must block app startup. Prod recreate and down/up retain volumes, keys and existing token lineage. Reset only affects the exact fresh dev project. Docker host root/operators can mount any volume or join networks: these tests do **not** claim protection against privileged Docker administrators.

## Capacity candidate and provenance

The only additional running capacity services are one Collector, one Prometheus and one Grafana OSS. `images.json` pins immutable official multiarch index digests. On 2026-11-16 the engineer fetched those index digests directly from authenticated Docker Hub registry API; every actual Linux run refetches and hashes the pinned index, requires Linux amd64 and arm64 child manifests, pulls by digest, and records actual selected image architecture. The application is built from the existing Dockerfile and records its image ID and exact source/input hashes. No application package or instrumentation is added.

| Container | Version | Official compatibility/reference |
| --- | --- | --- |
| `otel/opentelemetry-collector-contrib` | 0.145.0 | [versioned remote-write README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.145.0/exporter/prometheusremotewriteexporter/README.md), [versioned exporter factory](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.145.0/exporter/prometheusremotewriteexporter/factory.go), [Collector configuration](https://opentelemetry.io/docs/collector/configuration/) |
| `prom/prometheus` | v3.9.1 | [versioned release](https://github.com/prometheus/prometheus/releases/tag/v3.9.1), [remote-write receiver](https://prometheus.io/docs/prometheus/latest/feature_flags/#remote-write-receiver), [storage](https://prometheus.io/docs/prometheus/latest/storage/) |
| `grafana/grafana` | 12.3.3 | [versioned release](https://github.com/grafana/grafana/releases/tag/v12.3.3), [official Docker installation](https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/), [configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/) |

Collector OTLP/HTTP accepts a bounded 100-series synthetic gauge at one point per series per second. It uses memory limiter, bounded batching and the beta remote-write exporter with a **real 10-request `remote_write_queue`**, one consumer, finite 20-second retry and 64-KiB batch/request limits. Version 0.145.0's factory explicitly configures the exporter helper queue with **request** sizing; the README's older “OTLP metrics” wording does not establish units. Queue instrumentation must actually expose capacity 10 or the run fails. No queue is invented for a scrape-only exporter. The collector's numeric self-metrics are scraped every five seconds with bounded sample/label limits. No application, log, trace or broad host exporter is enabled.

Prometheus receives remote write and retains at most 24 hours/512 MB metric blocks, with finite query timeout/concurrency/sample limits. WAL/head and Grafana state add disk **outside** this block limit. Grafana requires local credentials; anonymous/signup, reporting, updates, plugin preinstall/update and news are disabled. All three services share only their internal owned network; their generator/control endpoints are explicitly loopback-only. No external exporter, plugin, cloud sink, alert receiver, Loki or Tempo exists. Normal dependency/image downloads occur before workload phases.

## Measurement and limits

The same actual Linux host records timestamps/source/run/attempt, kernel/architecture, CPU model/count, RAM/disk, Docker/Compose versions, image manifests, caps and five-second samples. CPU uses Docker's convention: **100% = one logical CPU**. The declared rehearsal CPU budget is the runner's reported logical CPU count, not Oracle's OCPU definition.

| Phase | Duration | Work |
| --- | --- | --- |
| Baseline | 120s | Both real app/PG environments, fixture proxies/sinks, no telemetry stack |
| Candidate idle | 120s | Both environments + candidate, no generated request/OTLP load |
| Loaded | 300s | 2 authenticated profile/avatar reads/s/environment, concurrency ≤4 each; 100 synthetic OTLP points/s; authenticated Grafana datasource query every 10s |
| Storage outage | 60s | Stop only synthetic Prometheus, retain offered app/metric/query load; observe bounded queue/retry/loss |
| Recovery | ≤120s | Restart same store/volume; observe resumed query-visible ingestion, drained queue, continued app reads |

The workload uses actual account and private photo reads plus database guards, with a normal login at each phase boundary. No authorization/rate bypass exists. Separate readiness sampling includes the real Alembic DB check. This is a narrow account/photo workload, not a complete marketplace production simulation. Proxy/sink container costs are reported separately in service samples; generator and sampling overhead appear in total runner CPU/RAM/load. The summary reports offered/scheduled/completed/error reads, achieved rate and p95/peak latency, OTLP accepted/rejected points, actual stored/query-visible counts/cardinality, Collector refused/export/enqueue failures and queue gauges. Offered OTLP samples are not assumed equal to stored samples or scrape count. A missed fixed target is a failure/limitation, never a successful target claim.

All running services have CPU/RAM/pid/log caps. Stop conditions are any unexpected restart/OOM/exit, app unhealthy >30s, sampler cadence failure, aggregate steady service CPU >80% of declared budget for 30s, service RAM >85% cap for 30s, free disk below max(4 GiB,20%), or queue beyond capacity. Controlled exporter loss is separately reported. Sampler output provides count/p95/peak and actual per-phase Prometheus total/WAL/head plus Grafana disk. Growth/hour/day and conservative doubled 24h/7d unretained projections include a fixed 1-GiB WAL/compaction/state reserve. Short-run allocation noise and asynchronous retention prevent a full soak/quota claim.

Hypothetical Oracle projection reserves at least **1.5 GiB** OS/Docker/proxy/transients and **20% CPU**, plus disk/log/backup reserve. The summary lists both app/DB budgets, migration/upload-init transients, proxies/sinks and candidate caps, measured deltas and explicit excluded future instrumentation/trace/log costs. There is no linear x64 vCPU → ARM OCPU equivalence. **Hosted activation remains blocked / capacity unproven**, even if local measurements pass. #103 must measure actual instrumentation, trace/log storage and full export overhead on the intended platform before complete hosted observability selection.

## Future preservation and cutover plan (not executed)

Owner decisions must first identify target host/project/resources, provider contracts #56/#88/#89, intended URLs/DNS/TLS/access, exact secret destinations, maintenance/downtime window, backup destination/retention, migration compatibility and #90 recovery acceptance. #87 requires tested platform artifact identity; #102 owns approved same-digest promotion and retirement of every production autopush path. Do not silently rename current Oracle demo “production”.

1. Inventory current #95/#96 public URLs, native ARM source/image provenance, Compose project, PG/uploads volumes, stable keys, running controller/configuration and known-good readiness. Preserve all of these until a separately authorized transition.
2. Review an aligned private DB dump, uploads and configuration/key backup at one coherent maintenance point, checksums/access/retention and an independently verified restore into separate resources. Inventory/storage headroom and an authorized downtime budget must be explicit. This issue performs no live backup, restore, reset or drill.
3. Verify forward/backward migration compatibility and previous image/config readability before deploying anything. Keep previous exact image/config and stable secrets available. Avoid destructive schema changes without separately accepted recovery.
4. During an authorized transition, stop if readiness, identity, hashes, private access, capacity or deadline fails. Restore the previous image/config first when compatible; preserve current database/uploads and never delete live volumes. Broader aligned data restoration requires #90's reviewed recovery procedure and authorization, not an improvised rollback command.
5. Verify final public health, private auth/data/upload hashes, selected release provenance, retained backups, controller state and intended autopush/promotion behavior. Abort to the preserved current demo if any required check is unproved. Only independent QA and the exact publication lifecycle may claim completion.

## Evidence status

Actual run URL/attempt, observed measurements, safe report hash and final exact commit are **pending**. Evidence will be linked here after runtime execution. Unit tests and configuration cannot substitute for AC1–AC9 runtime outcomes. Cleanup checks both owner labels before project-scoped down, checks no exact-owned containers/networks/volumes remain, removes the owned image, and deletes only the freshly created validated private directory. Expected failure scenarios use this same cleanup path.
