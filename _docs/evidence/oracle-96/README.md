# Measured additional Oracle source deployment (#96)

Restricted source deployment is activated. The dated records below prove actual
controlled rollback and normal automatic release of
`0f099f724d0e6591202914a1c7a4b4b382b07bfa`. They do not predict a later commit's
result. This report's own CI/deployment and latest-release verification are
recorded in [issue #96](https://github.com/240103098-code/Student_marketplace/issues/96)
before closure.

This bounded Oracle demonstration does not promote the exact CI-tested image,
complete feature E2E, establish teacher/provider acceptance, or implement
AWS CloudFormation/GCP Terraform. Issues #87/#86/#56/#88/#89/#90 remain separate.
This automation created no new cloud resources or account upgrades and enabled
no paid service.

## Access and source boundaries

After explicit consent for the credential destination and brief outage, a new
CI-only Ed25519 key was installed; the administrative key was not reused.
Independent checks verified exactly three encrypted secrets in environment
`oracle-demo`, one `main` branch deployment rule and zero tag rules. Repository
branch protection/required reviewers are not claimed. Thirteen installed checks
and seven actual restricted-key SSH denial probes passed, covering shell,
file-transfer, PTY/forwarding and narrow sudo. See [access results](access-boundaries.json).

Initial seven-file provenance references source `634f76b`. Only the controller was later
corrected under [issue #98](../oracle-98/README.md); its installed SHA256 is
`3dfd1d0ddb5570453f6431edbd9e8cab27e811886efd595ae21f1727ac2b48aa`.
Account/key/gateway/fixed templates were not reinstalled. The plugin lacked
secret creation, so the operator used the official GitHub REST sealed-box API
with isolated operator-only PyNaCl 1.6.2, cffi 2.0.0 and pycparser 2.23. No application
runtime dependency was added; SMTP/JWT/database values and the administrative
private key never entered GitHub.

The actual dependent workflow and server controller independently gate canonical
push/main, exact SHA/attempt/job results, current-main order and ownership under
an exclusive lock. The server uses separately installed reviewed controller and
templates, native ARM builds, stable private settings/volumes and no automatic
schema change. [Operations](../../oracle-cd.md) documents timeouts, resource
caps, backup limitations and key revocation.

## Failed-CI exclusion

The deliberately failing branch was never merged.
[Run 43287149217](https://github.com/240103098-code/Student_marketplace/actions/runs/43287149217)
executed 365 backend tests: 364 passed and the sole intentional probe failed,
with zero errors/skips. Required gate failed, deployment skipped and owned
resources were cleaned. This historical source predates the five issue #98 tests.
Its branch guard is also false: the [actual record](negative-ci.json) proves
combined live exclusion plus independent failed-gate regression coverage, not
an isolated failing-main experiment.

## Actual controlled failure and rollback

Initial source `634f76b` failed before its planned pause because of the issue #98 loader
bug. That ordinary recovery is **not** counted here; its unused marker was
archived/disarmed before this corrected sequence. All times below are UTC.

For corrected source `0f099f7`,
[run 43494934230/attempt 1](https://github.com/240103098-code/Student_marketplace/actions/runs/43494934230/attempts/1)
passed prerequisite CI, selected the exact source, consumed the root-only
one-shot marker and paused only its owned candidate app. The observer recorded:

| Actual event on November 13 | UTC | Result |
| --- | --- | --- |
| Candidate `0f099f7` healthy before pause | 19:50:21 | Readiness200 |
| Exact `0f099f7` paused, marker consumed | 19:50:24 / 19:50:42 | Timeout / HTTP503 |
| Previous `c386907` unpaused, no pending recovery | 19:50:54 | Readiness200 |

Deployment correctly reported failure; successful recovery was not labeled a
successful release. [Owned-container observations](controlled-health-rollback.json)
and [independent external correlation](controlled-observation-qa.json) identify
the exact phase. The 78 external observations also include ordinary backup/recovery
outages; total non200 count alone is not used as intentional-pause proof.

Independent [post-recovery checks](rollback-retention.json) at
`2026-11-14T18:55:53Z` confirmed all seven complete table/file hashes match the
private pre-drill baseline, one uploaded file remains, stable runtime/SMTP and
four volumes are unchanged, and previous `c386907` is healthy/unpaused. No active marker,
pending recovery, timer or fallback service remained. This later check is dated
separately from the actual November 13 pause. No schema downgrade, volume deletion,
secret rotation, authenticated request, email or application-data write was used.

## Fresh retry and normal automatic release

Root reran the initial job and both dependents as a complete fresh attempt 2,
with no new marker and no reuse of attempt 1 prerequisite jobs. All three [fresh jobs](normal-jobs.json)
succeeded: implemented checks, required gate and additional Oracle deployment.

[Attempt 2](https://github.com/240103098-code/Student_marketplace/actions/runs/43494934230/attempts/2)
passed 369 backend tests, 166 frontend tests and two real Compose Playwright tests,
with zero unexpected skips/errors/failures. All nine checks passed; Compose and
Playwright shared one CI image. [Fresh CI evidence](normal-ci.json) verifies
cleanup, 222 raw source inputs and artifact 14128055372 with its exact digest;
it is not the attempt1 artifact.

At `2026-11-14T19:03:00Z`, [passive observation](normal-observation.json) confirmed
running/committed source `0f099f7`, exact run43494934230/attempt2, matching image and
readiness200 with no pause/pending/active marker/new-generation consumed marker.
Independent [verification](normal-auto-deployment.json) at 19:04:30Z confirmed:

- Native ARM64 image`sha256:14c3b612ca6af3b0c8d787b76ed2867bacf0c8a6b000e9c810fc60a25a6f7fa1`, nonroot user, exact source/state/run/attempt.
- Trusted HTTPS/HSTS/static/readiness; complete seven-table/file state, stable runtime/SMTP and four volumes match the private baseline.
- No pending recovery, pause, active marker or recovery timer/service; no authenticated request, email or application-data write.

An independent [outside-VM check](normal-external.json) at19:11:37Z also verified
trusted HTTPS readiness200, actual React static content and HSTS without auth.

The CI x64 image and server ARM image are distinct. This is checked-source
deployment, not exact image promotion. Only child96 may close after its final
publication is independently verified; its parent issues remain separate.

## Evidence privacy

Records omit host addresses/fingerprints, private key/config paths, identities,
rows/object paths, private data/config hashes, cookies/tokens and raw Docker/SSH
output. Raw logs and baseline digests remain outside Git; only selected safe
status/provenance and raw-log integrity digests are public. Measurement fields
are preserved; Git may normalize JSON line endings. Records stay attributed to
observed source `0f099f7` and actual dates, not a future report commit.
