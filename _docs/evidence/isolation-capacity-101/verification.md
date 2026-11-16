# Issue 101: actual isolated Linux rehearsal

The disposable isolation and metrics-only capacity rehearsal passed at runtime source **`7a153312d9160c9b8e3ebc669a4d5c840cf08e31`**. Hosted activation remains **blocked / ARM capacity unproven**. This record does not claim actual application SDK instrumentation, trace/log storage, production promotion, or a new hosted environment.

## Exact provenance and verification boundary

- [Dedicated rehearsal: run 43880113023, attempt 1](https://github.com/240103098-code/Student_marketplace/actions/runs/43880113023/attempts/1), actual controller UTC **2026-11-16 13:54:20 through 14:11:54**. Artifact **14232403302**, seven-day retention.
- Full original safe JSON SHA-256: `ddf6a61fc55d1b2ad9fbc3a5f0c1cba2e7087c2a65aa3c11e694cc1e9f3584df`.
- Original artifact ZIP SHA-256: `7589c4371afec9686184d93e3ab7068fbc9bbdfbb61e32127c05fcd25f9ec777`.
- [Durable aggregate JSON](summary.json) retains every check, phase/service count/p95/peak, workload/queue/counter/window/storage value, host/tool metadata, all ten runtime input hashes, image index/platform-child digests and the application image ID. Repetitive sampling rows remain in the original allowlisted artifact; no raw logs, labels, mail, credentials or private payloads are copied.
- All ten runtime input hashes and all **229** ordinary-CI input hashes were independently recomputed from the canonical Git blobs at the runtime source. The evidence is in a **documentation-only descendant**: it does not pretend that the later documentation commit was the source of this run. Compare the final evidence commit against the runtime SHA: every runtime input remains byte-identical; Windows working-tree CRLF conversion is not used for this comparison.

[Existing full CI at the same runtime source](https://github.com/240103098-code/Student_marketplace/actions/runs/43880113006/attempts/1) passed: **410 / 410 backend tests**, zero skips/failures/errors; **166 / 166 frontend tests**; typecheck/build/mock exclusion/OpenAPI checks; real Compose; all four Playwright modes including the expected controlled failure; full cleanup. Its safe JSON hash is `f557ce35c909667482a6ae08a0abc4065e94605e099ef01849918d8c3a304ea4`, artifact **14233070728**. The extra local focused harness suite passed **31 tests**. Independent evidence/publication QA and ordinary CI on the final documentation descendant remain separate lifecycle gates; this document does not close the issue.

## Acceptance coverage

| Criterion | Observed result and boundary |
| --- | --- |
| AC1 | Distinct fresh dev/prod projects, DB identities/users/passwords, JWT/SMTP/leaf keys, PG/upload volumes, origins and exact network memberships. Synthetic prod actually uses `APP_ENV=production`, verified HTTPS and Secure cookies. Trusted browser navigation and host-only cookie transmission checks passed. |
| AC2 | Real normal register/verify/login and authenticated STARTTLS sinks; private profile/avatar upload and own read; anonymous, cross-JWT, cross-cookie, wrong-Origin and browser leakage denials passed. No fixture auth bypass or external mail. |
| AC3 | Real dev write, downgrade/upgrade, bad migration gate, exact reset, bad-secret startup and secret replacement preserved prod fingerprints/readiness/private reads. Current prod DB IP had a successful prod control and denied dev connection; dev DB credentials and prod service-name lookup were denied. Prod recreate/down-up retained DB/upload hashes and existing auth lineage. |
| AC4 | One pinned Collector, Prometheus store and Grafana OSS actually ran. Synthetic OTLP points were stored and queried through authenticated Grafana with the expected numeric value; this is capacity proof only. |
| AC5 | All five real phases below completed with the fixed offered read/metric/query workload, actual per-field intervals, service and whole-runner costs, disk/WAL/PG/upload sizes and latency/rate counts. |
| AC6 | Explicit service/queue/retry/retention bounds; real storage outage reached queue 10 / 10 and produced the measured deficit below. Fresh stored ingestion resumed within 4.033 seconds, queue drained, apps stayed ready. |
| AC7 | Normalized CPU, RAM/startup/disk reserves and strict stop parameters recorded. Short-run x64 results do not establish ARM/OCPU fit; hosted activation stays blocked. |
| AC8 | [Reviewed preservation/cutover plan](../../rehearsal101.md#future-preservation-and-cutover-plan-not-executed) covers current demo/controller/data/secrets, consent, aligned backup/restore verification, migration compatibility, stop/rollback and final health. No live cutover, backup, restore, reset or promotion occurred. |
| AC9 | Exact source/run/attempt, hashes, aggregate outcomes and actual owned cleanup are durable here. Final independent QA, exact publication and publication verification remain required. |

All **51** runtime checks were true. Both real app environments were ready at every one of **240** samples. Maximum actual repeated-field interval was **4.038939 seconds**, below the strict five-second limit. The three-second dispatch target, bounded workers, live ownership/state/OOM/restart/network inspection and actual timestamps are documented in [the controller guide](../../rehearsal101.md). A Docker host administrator is outside this isolation boundary.

## Host, dependencies and resource bounds

Actual Linux x86_64 runner: Intel Xeon 6975P-C, **4 logical CPUs**, **16,078,424 KiB RAM**, kernel `7.0.0-1014-aws`, glibc 2.39, Docker **28.0.4**, Compose **2.38.2**. Workflow toolchain pins are Python 3.13.15 and Node 24.19.0; ordinary CI observed npm 12.2.0 and PostgreSQL 18.6. Actual trusted Chromium was **151.0.7922.34** with existing Playwright **1.62.1**. TLS retained strict certificate/hostname checks with OpenSSL **3.0.13**.

New container references are official **Collector contrib 0.145.0**, **Prometheus v3.9.1**, and **Grafana 12.3.3**. Their immutable multiarch indexes and actual Linux/amd64 child digests are in `summary.json.images`; Linux/arm64 manifest availability is recorded, not ARM runtime testing. The existing application image/Dockerfile/locked dependencies are reused. The only added host test utility is Ubuntu's `libnss3-tools` for a temporary NSS trust database; standard-library proxies/generators add no application package. Official version/configuration references remain in [the guide](../../rehearsal101.md#capacity-candidate-and-provenance).

| Service (each environment where applicable) | CPU cap | RAM cap (MiB) |
| --- | ---: | ---: |
| app | 0.50 | 256 |
| db | 0.50 | 384 |
| migrate | 0.50 | 256 |
| uploads-init | 0.25 | 64 |
| smtp | 0.15 | 96 |
| proxy | 0.25 | 96 |
| collector | 0.50 | 192 |
| prometheus | 0.75 | 384 |
| grafana | 0.50 | 256 |
| control | 0.25 | 96 |

Every service also has PID limit **128** and JSON logs limited to **2 MiB x 2 files**. Collector memory limit is 128 MiB inside its 192 MiB container, bounded 100-point batches, 64 KiB request/batch limit, ten queued requests, one consumer and finite retry. Grafana anonymous/signup/analytics/update/preinstall/news are disabled. Backends are internal-only; fixture relays have loopback publications, fixed upstreams and their own ingress bridges. Relay network egress is not claimed to be firewall-denied.

Stops are any OOM/unexpected exit/restart; app unhealthy over 30 seconds; actual field interval over five seconds; service CPU aggregate over **320%** (80% of the declared four-logical-CPU budget) for 30 seconds; service RAM over **85%** cap for 30 seconds; free disk below max(4 GiB, 20% of filesystem); or queue beyond ten. Minimum observed free disk was **89,822,040,064 B**; maximum service RAM was **46.17%** of cap. No such stop occurred. Controlled exporter loss is reported separately.

## Actual measurements

**CPU 100% = one logical CPU.** Container RAM is Docker-reported memory; whole-runner RAM below also includes generator/probe/Docker/OS costs. Fixture proxy/sink/control costs and every service's count/p95/peak remain separately available in the aggregate JSON.

| Phase | Seconds | Samples | Max actual field gap (s) | Service CPU p95 / peak (%) | Service RAM p95 / peak (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 120.015 | 40 | 4.0175 | 55.78 / 65.14 | 310.63 / 312.28 |
| idle | 120.017 | 40 | 4.0121 | 69.23 / 74.12 | 455.48 / 462.83 |
| load | 300.007 | 100 | 4.0184 | 76.18 / 80.57 | 479.93 / 483.15 |
| outage | 60.002 | 20 | 4.0389 | 85.00 / 110.41 | 469.17 / 481.84 |
| recovery | 117.853 | 40 | 4.0326 | 96.26 / 104.88 | 487.51 / 501.03 |

| Phase | Whole-runner CPU p95 / peak (%) | Whole-runner RAM p95 / peak (MiB) |
| --- | ---: | ---: |
| baseline | 61.72 / 121.65 | 1440.52 / 1458.50 |
| idle | 63.55 / 70.40 | 1636.29 / 1653.77 |
| load | 78.25 / 87.77 | 1651.41 / 1659.16 |
| outage | 98.57 / 100.33 | 1660.22 / 1674.03 |
| recovery | 96.41 / 115.42 | 1672.85 / 1709.79 |

Loaded reads: **600 / 600 per environment**, no errors or scheduler rejection, **1.999951 successful requests/s** each. Dev p95 / peak latency **47.24 / 56.67 ms**; prod **68.70 / 85.19 ms**. Concurrency was at most four per environment. All **30,000 offered OTLP points** were accepted and independently query-visible as **100 series**; **30 / 30 authenticated Grafana queries** succeeded. Query counts use explicit phase-end evaluation times and millisecond source windows. Generator lateness and actual offer interval bounds are retained in JSON; these are account/photo reads, not a production marketplace traffic model.

During the measured 60-second storage outage, each app completed **120 / 120** reads without error; all 6,000 metric points were acknowledged by the receiver, while asynchronous downstream queue/export failures caused loss. Queue peak/p95 were **10 / 10** at capacity ten; six Grafana datasource-query failures were expected. Fresh post-restart stored data was actually observed **4.032815 seconds** after restart completion, including setup and query time. Recovery measured **117.853 seconds** inside the 120-second budget, completed **236 / 236 reads per environment**, accepted/stored 11,800 new points and passed 12 Grafana queries; queue drained.

After producer shutdown and a bounded **6.047-second settlement**, one fixed source window reconciled **47,800 accepted** against **42,700 exported/query-visible stored points**, an observed **5,100 accepted-but-unexported deficit**. Separately, failed-send attempt-points increased **1,200** and the final cumulative enqueue-failed counter was **3,900**; its baseline was unavailable/null. Failure attempts are not generally unique lost points, and missing counters were never invented as zero. Final receiver-refused was an actually observed zero. This is recovery of ingestion, not recovery of already dropped telemetry.

## Storage and cautious projection

Each app environment's loaded PGDATA was **66,281,472 B including 33,566,720 B WAL**; uploads allocated **16,384 B** each. Loaded PG/upload growth was zero. WAL is a subset and is not added twice. Phase start/end/growth and count/p95/peak for every environment are retained in JSON.

| Phase | Prometheus total allocated B, start -> end | End WAL / head B | End Grafana B |
| --- | ---: | ---: | ---: |
| idle | 20,480 -> 24,576 | 12,288 / 4,096 | 1,302,528 |
| load | 24,576 -> 458,752 | 315,392 / 135,168 | 1,302,528 |
| outage | 479,232 -> 479,232 | 335,872 / 135,168 | 1,302,528 |
| recovery | 487,424 -> 741,376 | 466,944 / 266,240 | 1,302,528 |

Loaded telemetry disk grew **434,176 B** over 300 seconds: approximately **5.21 MB/hour** or **125.04 MB/day**. Doubling that observed rate and adding a **1 GiB fixed WAL/compaction/state reserve** projects **1.324 GB / 24h** and **2.824 GB / 7d unretained**. Short-run allocation/compaction noise makes linear projection uncertain; this is not a retention soak or disk-quota proof.

The actual Prometheus flag is `--storage.tsdb.retention.size=512MB`. [Pinned v3.9.1 parsing](https://github.com/prometheus/prometheus/blob/v3.9.1/cmd/prometheus/main.go#L424) uses powers of two, so the enforced block limit is **512 MiB = 536,870,912 B**, with 24-hour time retention. The original controller report's `512000000` byte label is a decimal-unit metadata error, preserved and explicitly annotated in the aggregate; the original report/hash and measured growth are unchanged. Retention is asynchronous, and WAL/head add disk outside the retained-block cap.

Loaded service RAM peak was **483.15 MiB**; the measured amount plus a 50% margin fits the hypothetical 4.5 GiB remainder after a 1.5 GiB OS/Docker/proxy/transient reserve. Configured startup budgets separately include both app/PG stacks, migrations/upload initializers, proxies/sinks, telemetry and the control relay. Logs, aligned backups and at least max(4 GiB, 20%) free disk still need reserve. Loaded CPU peak **80.57%** and p95 **76.18%** are x64 logical-CPU measurements, not an Oracle ARM OCPU conversion. Reserve at least 20% CPU, retain **hosted activation blocked / capacity unproven**, and retest actual SDK instrumentation, trace/log storage/export and the intended workload under #103 on the intended platform.

## Cleanup, history and remaining gates

Actual cleanup removed exact-owned containers, networks, named volumes, the owned application image and private fixture files. Shared/default Compose and current Oracle controllers/workflow behavior were preserved. No private dataset/config, user's database on 55435, real SMTP/recipient, SSH/cloud secret or live resource was used.

Selected earlier diagnostics remain history, not acceptance: [1c26 TLS fixture failure](https://github.com/240103098-code/Student_marketplace/actions/runs/43767702881), [6c counter-readiness failure](https://github.com/240103098-code/Student_marketplace/actions/runs/43769282797), [cdc actual field-gap failure](https://github.com/240103098-code/Student_marketplace/actions/runs/43874061427), and [bbeee4 parent success](https://github.com/240103098-code/Student_marketplace/actions/runs/43876809014). None substitutes for the exact final 7a runtime linked above.

Only independent QA may approve the evidence commit; root then publishes that exact approved descendant. Ordinary CI must pass before main publication, and normal main CI/current Oracle CD remain part of publication verification. Closing #101 or activating a hosted layout is not authorized by this document; #102 and broader #90/provider/host transition gates remain separate.
