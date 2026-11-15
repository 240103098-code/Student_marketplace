# CI for the currently implemented tests (#92)

`.github/workflows/implemented-ci.yml` runs on **every push and pull request**, without branch/path filters. It is a partial infrastructure child of #86. Future feature specs #61–85, full #86 completion and main-only CD #87 remain separate. No deployment or registry publication exists in this workflow.

Stable check names are **CI / implemented checks** and **CI / required gate**. The final gate runs even when its dependency fails and succeeds only for the literal dependency result `success`; failed, cancelled and skipped verification all fail the gate. There is no `continue-on-error`, permissive aggregation, `pull_request_target` or secret-bearing configuration. Jobs use standard public `ubuntu-24.04`, read-only contents permission, bounded timeouts and checkout without persisted credentials. All actions are pinned to exact commit SHAs.

For reproduction, use Python **3.13.15**, Node **24.19.0**, npm **12.2.0**, Docker Engine/Compose v2 and OpenSSL on Linux. The workflow creates `.venv`, installs `requirements-dev.lock`, installs the isolated locked e2e package and matching Playwright Chromium revision. On a clean checkout:

```sh
npm install --global npm@12.2.0 --ignore-scripts --no-audit --no-fund
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
npm ci --prefix e2e --ignore-scripts --no-audit --no-fund
node e2e/node_modules/@playwright/test/cli.js install --with-deps chromium
.venv/bin/python -m tools.ci_checks
```

The controller refuses existing generated output and unexpected toolchain versions. It creates only a random named PostgreSQL container/volume with an exact ownership label, random credentials and an automatically assigned loopback port. The database is fresh, named `student_marketplace_test_<random>` and passed with its exact `TEST_DATABASE_CONFIRM` guard. No user's `.env`, database, SMTP account, checkout or persistent setup is read. The complete `python -m unittest discover -s tests -v` runs against that real database; dynamic counts must show success, a nonzero count and zero skips. The canonical `python -m tools.export_openapi --check` and exact 40-operation map validator run too. Counts are measured from the actual run, never copied from historical documentation.

Frontend verification installs the lock with `npm ci`, runs every Vitest test with two workers and a private JSON reporter, requires all discovered tests passed with zero pending/todo tests, runs typecheck/build and executes `node tools/check_frontend_build.mjs`. That last contract performs the real production build, checks mock-data exclusion and requires both mock build modes to fail. Native test/build output is captured privately; public evidence contains safe stage/count records instead of raw assertion output.

One candidate Dockerfile build is tagged with the generated CI owner and labeled accordingly. Its exact image ID, tag and ownership label are validated by both borrowers: the existing real Compose readiness/migration/persistence controller, then four fixed real authenticated-STARTTLS Playwright runs: original default smoke, collective full suite, registration-only, and original smoke intentional failure. They do not rebuild or delete that shared image. Their separate project names derive from the CI owner so the parent can attempt exact label-validated cleanup even if a child times out. Child temporary fixture directories live under the parent's private root. The parent removes the shared image only after every check, verifies absence and records the same image ID across the chain. Production runtime behavior and the default standalone controllers remain unchanged.

The Compose verification retains missing-secret refusal, readiness/migration/database-outage recovery, persisted real rows/private images/auth lineage across replacement/down-up, actual static/browser/API traffic and its deliberate failed-migration startup gate. The Playwright smoke retains two fresh UI signup/mail/verify/login journeys, fresh anonymous denial, explicit admin CLI provisioning and server-confirmed admin access. This smoke does not implement complete future feature assertions. Its expected-failure wrapper is not the deliberately red CI-gate proof.

Safe diagnostics are enumerated individually in the workflow: `summary.json`, the existing sanitized Compose JSON, #60 safe run/test/stage JSON and deliberately masked failure PNGs. No raw service/test/build logs, traces, HAR, video, storage state, error-context, environments/configs, private mail/certificates or expanded credential-bearing commands are uploaded. Artifacts expire after seven days. Cleanup runs in `finally`, validates exact labels before removing resources, attempts child project/container/network/volume cleanup, removes only generated owned PostgreSQL and the shared image, and removes only known generated outputs/private directories. A 55-minute verification job and two-minute gate provide an outer bound; a terminated ephemeral runner is the final boundary for forced process/host interruption.

A deliberately failing real unittest must be demonstrated on a separate reviewed probe branch with the same workflow. That branch must produce a failed implemented check and failed required gate. Do not merge the probe test, use `continue-on-error`, or call #60's successful expected-failure wrapper a red-gate proof. Actual positive push and PR runs passed on runtime head `4a4e99d539427b89a94855dee2038826139c4874`: 325 backend tests, 166 frontend tests and two Playwright tests passed with zero skips/pending tests. [Durable verified evidence](evidence/ci-92/README.md) records run links, hashes, versions, one-image identities and cleanup, plus initial genuine failing checks and a clean isolated one-failure probe whose required gate failed. This documentation/evidence follow-up changes no tested executable inputs.

Branch protection is **unapplied**. A repository administrator can protect main and require **CI / required gate** (and optionally its implemented dependency), require pull requests and select the desired review policy. This package documents those settings but does not claim configured enforcement. CD #87 cannot release until its own separately approved green-main contract exists.

## Safe operation diagnostics (#97)

An actual main prerequisite failure exposed a diagnostic gap before backend
discovery. Run43212254097 attempt1 at `b5dc1ec9643ea1cf2e346f31dd6d2776ecdaa594`
reported only `prerequisites/subprocess-status`. Attempt2 of that unchanged commit
passed325 backend tests with zero skips,166 frontend tests and2 Playwright tests,
all9 checks and owned cleanup. The original command/infrastructure cause remains
unknown; a retry without a code change is not evidence that it was repaired.
[Preserved observations and deterministic comparison](evidence/ci-97/README.md).

Every controller subprocess now requires an identifier from the fixed
`OPERATIONS` vocabulary in `tools/ci_checks.py`. Prerequisites distinguish
`source-revision`, `source-inventory`, `node-version`, `npm-version`,
`docker-version`, `compose-version`, `postgres-volume-create`,
`postgres-container-start` (including Docker's pinned-image acquisition),
`postgres-readiness`, `postgres-loopback-port` and `postgres-version`. Remaining
operations identify the existing suites/builds and label-guarded cleanup; labels
never come from commands, resource names, paths, environment or native output.

Failure summaries include `failure_operation`, `failure_class` and
`failure_timeout`. Classes distinguish `exit-status`, `timeout`, `process-start`,
`readiness-deadline`, `invalid-operation` and invalid validated metadata
(`invalid-result`). `failure_exit_status` is present only for an actually known
bounded integer, including zero for malformed output of a successful inspection.
Timeout/start errors do not invent an exit code. Missing/unapproved labels reject
before execution and report only `unapproved-operation/invalid-operation`.
Successful native version/revision output is syntax-validated before publication.

The first primary diagnostic is captured before cleanup. `cleanup_failures`
separately records bounded static operation/class/status entries and cannot
replace the original cause; failed cleanup still forces overall FAIL. Expected
nonzero readiness/absence probes retain their existing behavior. No new automatic
retry, raw logging, dependency, image, test-count bypass or gate exception was
added. Native stdout/stderr and arbitrary exception text remain private; safe
summary fields do not include argv, environment, private paths or identities.

Focused verification: `python -m unittest discover -s tests -p test_ci_diagnostics.py -v`
(12 passed) and `python -m unittest discover -s tests -p test_ci_gates.py -v`
(2 passed). They include real harmless exit/timeout/missing-process cases,
hostile output/argument/environment sentinels, unknown labels, readiness deadline
and primary-failure/cleanup preservation. Windows sandbox execution needs an
owned writable TMP/TEMP; that environmental setup does not skip any test. Actual
candidate full CI and final independent acceptance remain pending at this checkpoint.


The #61 selection checks reuse that one validated image but create fresh Compose database/upload/SMTP/limiter state for every mode. Each child has a 600-second outer deadline and its original bounded controller deadlines. Before continuing, CI checks the exact candidate and image, explicit selection/intention, actual test ID/status set, project cleanup and removal of private files. The expected-failure mode must record the student browser failure honestly after the complete student journey and controlled-failure stage; its successful controller outcome means the diagnostic contract passed, while the browser outcome stays failed.

Full-suite evidence retains the existing `ci-safe/e2e-*` names. The other fixed filename prefixes are `e2e-smoke-*`, `e2e-registration-only-*` and `e2e-intentional-failure-*`. Each archives only the explicitly allowlisted safe JSON/fully masked PNG files before removing the verified file-only `e2e-safe` directory and starting the next run. The workflow enumerates every artifact path. `summary.json` records each mode, its actual browser status/exit, and cleanup separately. Missing/mismatched evidence fails the required gate. This wiring makes actual Linux verification possible; acceptance still requires the resulting exact-commit runtime evidence and independent QA.


Actual #61 runtime verification passed on `02b39b22d784eb0652c7d6f32cdb9ed372b5c216`: 379 backend tests, 166 frontend tests, real Compose, default smoke two tests, full suite three tests and registration-only one test passed. The original intentional-failure child correctly recorded one actual failed student/exit 1 after its complete journey; the parent accepted the unexecuted admin without inventing a result. One owned image served all fresh stacks and all cleanup passed. [Durable evidence and earlier failure history](evidence/e2e-61/README.md) identify the exact Linux run, artifact and input hashes. Candidate-branch Oracle deployment was skipped; final main verification and publication/closure are separate.
