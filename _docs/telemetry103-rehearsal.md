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

GitHub push runs preflight. Dispatch `phase=full` runs functional/capacity as
separate bounded jobs at the selected candidate branch. Each has30min job limit,
<=120s setup,<=1570s controller work and<=90s owned cleanup. Preparation has240s,
app transitions90s cumulative, privacy fixture20s. Capacity workload worst-case
1200s plus those budgets/settle remains below the job limit; a missed budget fails
rather than truncating phases or calling incomplete evidence passing. No `all`
mode attempts a >30min combined run.

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
file<=512KiB, allocated data+directory blocks<=128MiB,<=16384files and24h maximum
age; oldest files evict, oversize refuses. Private files never upload. Per-signal
filesystem/inode reserves are accounted separately in capacity planning.

Only owned internal networks connect services; dev/prod application storage and
DB networks remain separate. Fixed loopback control relays are operator access;
their own ingress bridge has a default route, so there is no claim of enforced
relay egress denial. Docker administrators are outside this trust boundary.
Local OTLP is unauthenticated only within these disposable trusted networks.
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

The privacy fixture adds actual PostgreSQL parameter/error probes and fixed-log
extra attempts outside measured phases. Normal HTTP work still uses guarded API
routes. Unique canaries cover path/query/header/body/SQL/error/log extra/resource/
propagation/ambient configuration. Strict decoded schema and literal/URL/base64/
hex/JSON searches cover all signals and private diagnostics. Artifact uploads
allow only the constructed numeric/hash/boolean summary for seven days.

Current local checks: six controller/receiver safety tests pass; thirteen retained
SDK/lifecycle/privacy tests pass. Linux live receipt and complete phase evidence
are pending. Before publication readiness, finish conservative allocated-storage/
WAL/backup projections, paired variation reporting and actual platform-child
manifest validation, then independent QA must audit the exact candidate.

Official pinned source references: [OTLP HTTP factory/maturity](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.145.0/exporter/otlphttpexporter/factory.go),
[queue sizing/batching](https://github.com/open-telemetry/opentelemetry-collector/blob/v0.145.0/exporter/exporterhelper/internal/queuebatch/config.go),
[Prometheus remote write maturity](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.145.0/exporter/prometheusremotewriteexporter/metadata.yaml).
