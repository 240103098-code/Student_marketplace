# Explicit local telemetry (#103)

Telemetry is disabled by default. `TELEMETRY_ENABLED=true` explicitly opts in;
`TELEMETRY_ENDPOINT` is an OTLP HTTP origin (default loopback4318, fixture
`http://collector:4318`). This package does not enable anything on Oracle.
`TELEMETRY_SERVICE` permits only `student-marketplace`; `TELEMETRY_VERSION`
permits a bounded numeric release/hex commit identifier (64 characters maximum).
Environment is the existing development/test/production enumeration. No global
SDK providers, handlers, instrumentors or resource detectors are installed.
Providers/workers/sessions/listeners are created in lifespan only; borrowed
engines retain ownership and callbacks are removed individually on exit.

The installed candidate is API/SDK/OTLP HTTP1.45.1, Python>=3.10 (application
requires>=3.11). Minimal new direct dependencies are API, SDK and OTLP HTTP;
resolved runtime additions are SDK, HTTP exporter, HTTP transport0.66b1,
OTLP common0.66b1, proto common/proto1.45.1, semantic conventions0.66b1,
googleapis-common-protos1.76.0, protobuf7.36.2, requests2.34.2,
charset-normalizer3.5.2 and urllib32.8.0. Both lockfiles use the shared exact
runtime export; requirements-dev.lock includes requirements.lock.
Installation resolved successfully on Python3.13.15. The new transport/common
0.66b1 packages are mandatory SDK exporter dependencies, not broad automatic
instrumentation. [Official Python documentation](https://opentelemetry.io/docs/languages/python/)
marks traces/metrics Stable and logs Development. Logs therefore retain upgrade
risk. Direct `Logger.emit` is supported by the installed SDK; deprecated
`LoggingHandler` is unused. [Release source](https://github.com/open-telemetry/opentelemetry-python/releases)
and [instrumentation documentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
were checked2026-11-17. Actual pinned Collector compatibility remains a runtime
acceptance gate, not inferred from release numbers.

The complete emission schema is deliberately narrow:

| Location | Allowed values/bounds |
| --- | --- |
| Resource | Exactly service.name, service.version, deployment.environment.name above; no SDK default resource creation |
| Scope | marketplace.safe, version1; no caller-defined scope/schema |
| Server span name | Fixed http.request |
| DB span name | Fixed db.operation |
| HTTP span/metric attributes | http.route from finite router templates or unmatched; method GET/POST/PATCH/DELETE/PUT/HEAD/OPTIONS/OTHER; status_class1xx–5xx/other; outcome success/error |
| DB span attributes | db.system.name postgresql/sqlite; db.operation.name SELECT/INSERT/UPDATE/DELETE/BEGIN/COMMIT/ROLLBACK/OTHER; outcome success/error |
| Span events/links | Disabled, count0; no exception recording/status descriptions |
| Logs | Fixed http.request.completed body/event, INFO severity; no extras/exception/attributes accepted |
| Metrics | Fixed http.server.requests, http.server.request.duration, process.cpu.time and process.memory.usage; empty descriptions; fixed units; only finite HTTP attributes above; runtime metrics have none |
| Correlation | Synthetic trace/span IDs; exact one version00 traceparent55bytes, nonzero lowercase hexadecimal IDs, sampled bit only; all baggage/tracestate ignored |
| Exemplars | Explicit trace-based SDK filter; attributes already safe; actual stored receipt must establish correlation |

No emitted field reads cookies, auth, identity/domain IDs, query/body, raw path,
SQL parameters/text, exception objects, environment resources or process args.
The HTTP router object supplies its trusted template after handling. SQL reads
only the first keyword and immediately converts it to its finite enumeration.
All spans have <=8 attributes, <=128 characters/value; templates are finite
source code. Metric cardinality is bounded by finite routes*8methods*6classes*
2outcomes; no trace ID is a label. No arbitrary public emission API exists.

SDK trace/log batch queues are128 records, max batch32,1s schedule. Sampling is
100% locally (parent-based, honoring unsampled remote parents). Each HTTP export
has1s total SDK retry budget,0.2s connect/0.5s read timeout and64KiB serialized
request limit. The supported requests Session hook rejects ambient proxy/netrc,
header forwarding and redirects, verifies HTTPS certificates, and removes error
response text before SDK diagnostics. Resource detectors remain off. The pinned
SDK public BatchSpan/Log processor shutdown ignores export_timeout_millis;
small documented subclasses use its shared internal shutdown(timeout_millis=2500)
boundary. Trace+log shutdown therefore has5s aggregate allowance, followed by
metric shutdown with the remainder of8s. Pin upgrades must reverify this internal
boundary. Actual end-to-end shutdown remains a required<=10s measurement.

The private rehearsal receiver is one independent process/directory per signal.
It accepts only uncompressed protobuf,<=64KiB/request,<=2048 records/request,
<=512KiB decoded file,<=4096 files and<=128MiB per signal. Oldest files evict
at capacity/24h; oversized records refuse. Single-threaded HTTP and2s I/O timeout
bound concurrency/slow clients. Private directories/files use0700/0600. No raw
records are available through HTTP or artifact upload. Offline audit reconciles
duplicate deliveries by signal identity. Ephemeral local storage does not prove
production queryability or7day retention capacity.

Current verification: eight focused tests pass on Windows, including actual
SDK HTTP protobuf receipt, normal registration/verification/login and DB child
spans, controlled parent/log correlation, canaries in query/path/body/SQL/error/
extras, disabled subprocess absence of SDK/workers/export sessions, shared-engine
apps/repeated lifespan, absent Collector shutdown and receiver/config bounds.
These focused tests are not the required actual Collector/Linux capacity evidence.
The Linux phase design and measured evidence will be added before QA handoff.
