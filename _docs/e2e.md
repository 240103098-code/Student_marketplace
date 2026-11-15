# Isolated Compose Playwright harness (#60)

The root `e2e/` package pins `@playwright/test` 1.62.1 and its matching Chromium/headless-shell revisions through the npm lockfile and Playwright browser manifest. This isolates three development packages from frontend/runtime dependencies. The application image, Dockerfile, base Compose file and migrations are unchanged; `.dockerignore` excludes this harness. The SMTP service reuses that image solely as an available Python interpreter with a test script mounted at runtime.

Prerequisites: Docker Engine with Compose v2, Python 3.11+, OpenSSL, Node 24.19.0/npm 11.17.0 (the verified runner versions) and Linux are the supported complete-stack environment. The narrow `issue-60-e2e` GitHub-hosted Ubuntu workflow is disposable verification, not deployment or general CI. Local Windows has no Docker engine; local contract/TLS tests cannot establish a Compose PASS.

From the repository root:

```sh
npm ci --prefix e2e --ignore-scripts --no-audit --no-fund
node e2e/node_modules/@playwright/test/cli.js install --with-deps chromium
python -m tools.check_e2e_map
python -m unittest tests.test_e2e_harness -v
python tools/e2e_stack.py
# Preserve reviewed safe evidence before another independent run:
mv e2e-safe e2e-positive
python tools/e2e_stack.py --intentional-failure
```

`npm test --prefix e2e` and `npm run test:failure --prefix e2e` are equivalent when invoked from the repository root. Each controller command starts, tests, diagnoses and stops its stack in a `finally` block. Startup has a 150-second Compose health deadline, builds 600 seconds, browser process 210 seconds, each test 90 seconds, suite 180 seconds and shutdown 75 seconds. The workflow job has a 25-minute outer limit. The intentional run must finish the student registration/verification/login/reload/anonymous-denial journey before its deliberate assertion fails; its controller returns success only when that failure and cleanup are both demonstrated. `tests.json` still records the browser failure honestly.

Only the controller entry point is supported. Exactly one worker, one Chromium project, the fixed selected test set, no retries, no shards or additional CLI test options are supported. The controller rejects parallel/retry environment overrides; the reporter independently rejects worker/project/test-count overrides. Each test receives a newly created Playwright browser context, random university identity and random password. A separate fresh context proves anonymous API and UI denial. Two fresh accounts stay within the real registration/email quotas. Each independent controller run creates fresh application/limiter state, database, upload volumes, mail directory and secrets. No rate-limit override, shared account, data reset or mocked API exists.

The generated Compose project has a random 20-hex suffix. The controller supplies an explicit empty env-file and a restricted child environment, never reads `.env`, and publishes only the app on a random loopback port. Existing migrations, PostgreSQL health and private-upload initialization run normally. The private SMTP network is internal, has no published ports and cannot relay mail; only authenticated university messages of the exact registration purpose are accepted. STARTTLS performs a real handshake with a generated one-day CA/server certificate and hostname verification. `SSL_CERT_FILE` is mounted only into the test override app; certificate verification is never disabled and `SmtpSender` is unchanged. The app receives only the public CA certificate plus the registration-only read-only script and identity prefix, never the inbox, key or fixture configuration.

UI signup creates the eligible account, the trusted Node fixture reads one new private message correlated to that unique recipient and registration purpose, enters the actual code in the UI, deletes that inbox file, verifies and signs in. The admin fixture follows the same normal verification journey before invoking the existing `python -m backend.admin --email` operator command through the controller. It then signs in and proves the current admin access screen. There is no SQL role update, default admin or public role/code endpoint. This smoke does not prove complete #61–#85 feature acceptance.

On normal return or a caught failure, cleanup validates container, volume and network project labels/names before project-scoped `compose down --volumes`, verifies absence, removes only its unique image tag, and removes only its generated private temporary directory. There is no global prune. Hard process/runner termination cannot execute Python `finally`; an ephemeral hosted runner supplies the outer boundary. For local interrupted runs, inspect the exact generated project labels privately and stop only that known owned project; never infer ownership from a broad name prefix. Start/debug/test/stop are the same bounded controller command; there is no supported persistent debug mode that retains secrets.

Public diagnostics are strictly allowlisted: fixed logical stage names/completions, status/counts, test IDs, runtime versions, SHA-256 inputs, image ID, result and cleanup booleans. A failure screenshot masks the whole HTML document. It preserves viewport/browser evidence without publishing account content. The private subprocess boundary captures all Playwright/Docker/OpenSSL output and suppresses native errors. Traces, HAR, video, storage state and automatic screenshots are disabled; Playwright native output/error context stays in the private runtime directory and is removed. Never upload native reports, runtime directories, Compose config, service logs, environment, inbox, keys, cookies or browser request/response bodies. The workflow enumerates safe JSON/PNG filenames individually, with seven-day retention. Useful debug information is the last started and last completed logical stage, actual API response counts/statuses and cleanup status; inspect private state only during an authorized local run.

`e2e/operation-map.json` covers exactly the 40 canonical method/path pairs in JSON-compatible `openapi.yml`. Each row names its issue and dedicated spec path; only POST /auth/register is `implemented`, with all other rows `smoke-only` or `planned`. #77 owns categories/combined filters; #85 is explicitly cross-cutting across every operation. Planned paths are intentionally not placeholder implementations. `python -m tools.check_e2e_map` rejects missing/extra/duplicate operations, wrong counts, invalid issue coverage or false implemented statuses. The map never closes an issue; independent real-stack QA and exact-commit publication remain required.

Durable evidence must include actual positive and intentional-failure `run.json`, test/stage records, controlled SMTP completion, browser/revision and exact candidate/input hashes. Actual remote execution passed on 2026-11-03: see [durable evidence](evidence/e2e-60/README.md). Independent QA must verify the exact runtime candidate, this evidence-only follow-up and remote publication before closure. This docs-only follow-up preserves all tested input hashes and does not imply a new runtime execution.


## Registration feature (#61)

The dedicated `e2e/features/issue-61.spec.cjs` is selected through fixed controller options:

```sh
python tools/e2e_stack.py --selection registration
# Preserve/move the allowlisted safe directory before each independent command.
python tools/e2e_stack.py --selection full
python tools/e2e_stack.py --intentional-failure
```

The default remains the original two-test smoke selection. `full` adds the registration contract to both smoke journeys and is now the collective implemented CI command. Intentional failure accepts only the smoke selector and retains the complete student journey gate, honest failed browser record and cleanup requirements. Each command owns a fresh stack. The feature makes four real registration POSTs (201, 409, controlled SMTP 503, restored 201), plus two for collective smoke: six of the actual ten/IP/hour allowance. Invalid domains and 11/129 passwords are rejected by the actual React validator, with safe feedback, zero registration requests and read-only before/after absence checks. The form uses `noValidate`; malformed email browser invalidity is also checked without attributing a nonexistent API 422.

The registration test never verifies its accounts. A script mounted only into the disposable app reads exact run-prefixed synthetic identities using a PostgreSQL read-only transaction. Only fixed snapshot/compare operations exist; it returns counts and boolean predicates. Only SHA-256 baseline digests remain inside disposable app tmpfs; raw rows are never persisted or emitted. Password hash verification uses the existing Argon2id contract; hashes and codes never enter safe evidence. No public endpoint or application source changes are needed.

The private authenticated STARTTLS sink appends per-recipient delivery outcomes, including duplicate attempts. A test-owned private marker makes the real SMTP DATA command reject with 451; the real API then returns 503 and its database transaction rolls back. The marker is removed in `finally` and the UI retries normally with a 128-character password. The first keyboard submission accepts a 12-character password and normalized trim/case address. Every successful account remains unverified with exactly one registration code and no refresh session.

Explicit new safe filenames are `registration-stages.json` and wholly masked `registration-masked.png`; collective CI copies/uploads only these plus the existing allowlist. The stage vocabulary is fixed, IDs cannot collide with smoke, and reporter selection requires the exact expected title set. Runtime input hashes include the new spec and read-only script. Only POST /auth/register is marked implemented in the forty-operation map. Actual Linux registration/full/default-smoke/intentional execution and cleanup passed on runtime `02b39b22d784eb0652c7d6f32cdb9ed372b5c216`; see [durable #61 evidence](evidence/e2e-61/README.md). Independent runtime QA accepted that exact candidate. Final main CI/CD and publication verification remain required before closure; local contracts alone do not establish browser acceptance.


The implemented CI chain now exercises default smoke, full, registration-only and original intentional failure on the same single owned image, with a fresh stack per mode. It preserves safe artifacts under separate explicit prefixes and requires candidate/image identity, actual test outcomes and cleanup for each run. See [CI reproduction and evidence](ci.md). The legacy `issue-60-e2e` workflow and standalone default smoke selector retain their original behavior.


Registration response privacy checks passively clone the actual native browser fetch response for the exact same-origin POST `/api/auth/register`, before returning the original Response to the application. The observer forwards the original fetch receiver/arguments once; it neither substitutes a response nor sends another request. It keeps body observations only in private browser/Node memory, matches status and per-page sequence, rejects redirects, and fails generically after a bounded five-second wait or clone failure. This avoids the demonstrated Playwright inspector body-read hang on a 409 whose original body the application does not consume. The password/code/hash leak assertions still inspect the actual response body. The observer source is included in runtime input hashes; bodies never enter artifacts, browser storage or native reports. Fixed duplicate-step and main-stage elapsed timing records identify any later wait without exporting native errors or private values.
