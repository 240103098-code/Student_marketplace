# Disposable three-signal rehearsal design

This is an implementation-stage design, not completed runtime acceptance. Actual
Collector receipt, phase results and exact Linux runs remain required before
parent #103 can pass. Existing #101 source/evidence is unchanged.

The opt-in `tools.rehearsal103` reuses #101 owned dev/prod PostgreSQL, TLS SMTP,
verified HTTPS app proxies, immutable Collector/Prometheus/Grafana candidate and
label-checked cleanup. Registration/verification/login and read workload use the
supported actual API; no account or role is seeded directly. The two app modes
use the same local built image. No Oracle/deployment/secret/public endpoint is
changed. Each job records its source/image/input/config/phase-plan hashes,
run/attempt, host description and actual timestamps. Measurements from separate
hosts are never combined as an instrumentation overhead comparison.

| Job | Required work on its one documented Linux host |
| --- | --- |
| preflight | Actual three-signal receipt/privacy/propagation/exemplar/config/cleanup check, 15s baseline; explicitly no capacity acceptance |
| capacity | Three alternating-order pairs of120s off/on at2 actual reads/s/environment;300s enabled;60s Collector outage and fresh recovery<=120s; same-host overhead and complete capacity projection |
| functional |15s baseline;12s actual paused-Collector SDK queue saturation; separately stop Collector, trace sink, log sink, metrics sink and Prometheus for60s each, fresh recovery<=120s each; privacy/correlation and unique receipt reconciliation |

Trusted push `issue-103-otel-preflight` runs preflight; trusted push
`issue-103-otel` runs the functional/capacity matrix. Manual dispatch is optional,
never the prerequisite for candidate-only testing: GitHub documents a default-
branch workflow requirement. Main does not run these opt-in jobs.

Each30min job has an inclusive ledger: setup120s, controller work1520s,
verified owned cleanup90s, artifact step60s and platform handoff10s. Work includes
preparation210s, app transitions40s, measurement/support1200s, capacity correlation10s,
settle/flush12s, final two-app shutdown30s and audit/projection18s. Functional uses
measurement1190s and privacy20s instead. Nested charges count once and include
normal logins, queue drains, final sampler/Grafana calls and network probes.
Mandatory durations are never shortened; a missed shared cap fails and cleans up.
This does not promise every individual network timeout maximum fits at once.
Identical modes are reused; normal tokens renew before the requested phase plus
60s safety approaches the actual15min TTL.

Collector0.145.0 canonical `otlp_http` exporter is Stable for traces/metrics/logs;
legacy `otlphttp` is deprecated. Retained Prometheus remote write is Beta.
Each actual exporter has a2-request queue, one consumer, nonblocking overflow,
5s retry window,1s HTTP deadline and explicit16-item queue batch/100ms flush.
The pinned default queue batch is8192items; relying on it would violate bounded
receiver payloads. Collector memory limiter128MiB, batches16 and64KiB receive
cap remain explicit. Only the app's three safe resource fields become Prometheus
labels, separating dev/prod series without collecting new identity data.

Trace/log/metrics each have a separate private protobuf receiver process and
directory, enabling independent outages. Requests<=64KiB/2048records, decoded
file<=512KiB, allocated data+directory/stats blocks<=128MiB,<=16384files and24h maximum
age; oldest files evict, oversize refuses. Private files never upload. Per-signal
filesystem/inode reserves are accounted separately in capacity planning.

Only owned internal networks connect services; dev/prod application storage and
DB networks remain separate. Fixed loopback control relays are operator access;
their own ingress bridge has a default route, so there is no claim of enforced
relay egress denial. Docker administrators are outside this trust boundary.
Own app/DB reachability and cross-environment app8000/DB5432 denial are probed
after telemetry joins. Collector/control are privileged trusted fixture peers
across both telemetry networks. Fixed relays expose only telemetry/health, not
app8000 or DB5432. Local OTLP is unauthenticated only inside these trusted networks.
Any broader deployment requires authenticated, verified TLS and separate approval.

The fixture wrapper is identical in both modes. Disabled mode imports no SDK and
has no export workers/transports. Enabled observations delegate actual pinned SDK
processor callbacks, counting emitted/sampled records, actual queue-full drops
and exporter submission. Queue length is an observed value, not an inferred drop.
All observer/generator costs remain included. A local health plane is separate
from app readiness; final shutdown requires actual reported duration<=10s and
zero remaining SDK workers. Safe numeric attempt counters are not unique loss.
Offline decoded IDs reconcile generated, attempted, acknowledged, duplicated,
stored and missing records after settle; no dropped-data recovery is claimed.
Receiver counters persist across destination restarts; refused requests, known
refused records, unknown-count requests and evicted files have separate units.
Any unexpected refusal or eviction prevents a complete-window privacy PASS.

The privacy fixture adds actual PostgreSQL parameter/error probes and fixed-log
extra attempts outside measured phases. Normal HTTP work still uses guarded API
routes. Unique canaries cover path/query/header/body/SQL/error/log extra/resource/
propagation/ambient configuration. Strict decoded schema and literal/URL/base64/
hex/JSON searches cover all signals and private diagnostics. Artifact uploads
allow only the constructed numeric/hash/boolean summary for seven days.

Current local checks: eight controller/receiver safety tests pass; fourteen retained
SDK/lifecycle/privacy tests pass. Linux live receipt and complete phase evidence
are pending. Before publication readiness, finish conservative allocated-storage/
WAL/backup projections and paired variation reporting. Actual selected child
manifest/config identity verification is implemented but not yet run on Linux.
Independent QA must audit the exact candidate before runtime publication.

Initial actual Linux preflight at9bd8de6, run44303541026, failed with
sampler-overlap after3.054s of its baseline. No complete sample was recorded,
so this proves neither three-signal receipt nor capacity. Config validation,
normal guarded journeys and network/auth checks passed; owned image/private files
were removed and cleanup took55.602s. Ordinary regression CI44303540687 passed
separately at that source.

The sampler correction keeps its3s target soft while allowing one pending
snapshot; actual per-field gaps and first snapshot completion remain<=5s. Actual
inner probe failures are surfaced with fixed stage timings/partial timestamps.
Each command/read stays bounded, cancellation stops new commands, and snapshot/
nested workers join before resource cleanup. Failed join time consumes the same
90s cleanup reserve; it is never hidden behind Future.result(timeout). Five
focused scheduler tests cover3.2s deferral,>5s failure, inner-error propagation,
single pending work, actual cooperative thread joining and remaining cleanup.
An independently approved Linux rerun is still required.

The6ee6d92 rerun44306867668 surfaced the underlying storage-probe subprocess
failure instead of masking it as overlap. It recorded no complete sample; native
paths/error text were not published. Docker CPU collection took2.562s; verified
cleanup took54.308s. There is still no three-signal receipt or capacity PASS.

Store observation now validates exact owned read-only volume mounts and each
store's actual nonroot runtime UID/GID. A stat-only legacy-access probe publishes
only fixed role/category diagnostics; measurement executes as that verified
store owner inside the existing read-only observer. Relay identity/caps and data
permissions never change. Unknown owners/mounts/errors, symlinks and unexpected
devices fail rather than produce zeros; absent optional WAL/head directories
are explicitly marked absent. Linux preflight must show the actual access
category and positive same-owner measurements. Windows local guard tests pass
with native symlink permission unavailable; Linux CI must execute that guard.

Official pinned source references: [OTLP HTTP factory/maturity](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.145.0/exporter/otlphttpexporter/factory.go),
[queue sizing/batching](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.145.0/exporter/exporterhelper/internal/queuebatch/config.go),
[Prometheus remote write maturity](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.145.0/exporter/prometheusremotewriteexporter/metadata.yaml).

At059169a, actual preflight44363055329 reached all three receiver handlers and
eight complete samples (maximum observed field gap3.592s). Last sampled receipt
counters were421 spans,115 logs and1580 metric datapoint observations, with zero
refusals/evictions. The final decoded privacy/correlation audit did not run:
settle exceeded its12s allowance (12.353s), because an active8s workload/sampler
phase actually took9.347s before the additional3s sleep. Both actual SDK shutdowns
took about0.0022s and left zero workers; verified owned cleanup took52.220s.
This is partial wire progress, not a three-signal audit or capacity PASS.

The corrected final drain stops and joins workload/sampler first, then verifies
both real SDK shutdowns. It makes only Collector/receiver observations afterward,
with a shared absolute12s deadline including every connect/read/poll. There is
no active settle workload or blind sleep. Four explicit queue observations and
the actual accepted/sent/failed/refused/received counters must remain unchanged
with empty queues for8s. Missing supported counters fail; lazy failure counters
remain absent/unknown until observed, never fabricated zero. Counter resets,
unexpected refusal/eviction, late observation or insufficient quiet time fail.
Failure retains prior safe polls; final offline raw audit still reconciles unique
identities and proves privacy/correlation. The original total ledger is unchanged.

The8s quiet horizon conservatively rounds up processor batch1s + queue batch0.1s
+ retry start deadline5s + final HTTP attempt1s. Pinned0.145
[retry sender](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.145.0/exporter/exporterhelper/internal/retry_sender.go)
checks whether the next retry starts before its elapsed bound; the
[timeout sender](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.145.0/exporter/exporterhelper/internal/timeout_sender.go)
applies timeout to each attempt. Empty queue size alone cannot exclude in-flight
work. Late counter changes restart the entire quiet window within the same12s;
the controller fails instead of extending its deadline or claiming a drain.
