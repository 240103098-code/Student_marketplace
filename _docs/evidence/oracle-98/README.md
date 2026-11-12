# Runtime retention-loader correction (#98)

This records an actual deployment failure and its bounded correction. It does
not complete the separate automatic-release/health-drill criteria of issue96.

## Observed failure

Actual [main run43287631035, attempt1](https://github.com/240103098-code/Student_marketplace/actions/runs/43287631035)
used source `634f76b1e33c5013820b443105c097cddbba76de`. Required CI passed, but
activation failed before the operator's one-shot health marker was consumed.
The original application recovered ready/unpaused, with no pending recovery.
The observer saw ordinary stop/recovery outages, **no paused candidate and no
completed intentional health drill**. The unused marker was privately archived
and disarmed before any later attempt.

The embedded retention program constructed `Settings()` directly. That class
intentionally accepts explicit initializer settings only, so the constructor
ignored the real container environment and reported a missing JWT field. This
does not mean the configured application's secret was absent. Independent
read-only runtime probes confirmed that the established
`load_settings(env_file=None)` succeeds with that same production environment.
No settings values or raw errors are included here.

- [Measured early-failure observation](early-failure.json)
- [Safe actual-container diagnostic](runtime-loader-diagnosis.json)
- [Parent emitted-program counterexample](parent-counterexample.json)

## Bounded code and regression

Only the embedded program's import/call changes to the established explicit
loader. Backend settings isolation, seven table hashes, relative image paths and
bytes, symlink checks, fail-closed comparison, deployment gates, recovery and
schema compatibility are unchanged. No application credentials, schema or data
fixture is added to the deployed application.

The parent counterexample executes the actual emitted program against a guarded
disposable PostgreSQL database with all seven retained tables populated by
synthetic fixtures and a real temporary PNG. It fails for the observed missing-JWT
constructor reason. The same test passes after the correction. Its only program
mapping redirects the fixed upload-root AST literal into an owned temporary
directory; the real loader and SQL run unchanged. Test-only resource cleanup
models the real short-lived subprocess exit, and never changes production code.

Five new tests cover the real nonempty database/file snapshot, repeatability and
no mutation, path/byte changes, symlink rejection, missing/invalid environment,
refusal to read an env file/contact SMTP, and sanitized public failure diagnostics.
All32 focused tests (27 existing plus five new) passed locally with zero skips:

```text
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_oracle_cd*.py" -v
```

This requires the documented explicitly confirmed disposable PostgreSQL setup.
Actual candidate CI and the installed nonempty snapshot proof remain pending in
this checkpoint; local tests are not represented as completed live proof.

## Reviewed controller-only replacement boundary

Before replacement, independent QA must approve the exact candidate, its actual
complete CI and raw Git-blob bytes. Hold the existing
`/opt/student-marketplace-cd/deploy.lock`, require no pending/active deployment,
and independently confirm the original healthy source/image. Reject links,
unknown hashes, ownership or modes. The expected original controller SHA256 is
`aeb7d911ec861aa4f3108f1a50d37c3dac2aa2785f9aa5db9867d71e25d43948`.

Preserve that original root600 file privately, validate the new canonical hash,
and atomically replace only `controller.py`, retaining root ownership/mode0600.
Do not rerun the installer or change account/key, SSH/sudo, GitHub environment,
private runtime/SMTP files, persistent volumes or application image. Afterward,
independent quiescent `Host.retained()` calls must agree for the real nonempty
account/image state while readiness, original source/image and volumes remain
unchanged. Publish classifications/counts/provenance only, never private hashes,
identities, paths, values or raw output. Publication/closure follows that proof.

The remaining issue96 drill requires a fresh source/generation marker under the
existing owner authorization. The failed original attempt must never be relabeled
as that intended proof. Exact CI-tested image promotion, full feature E2E, provider
acceptance and AWS/GCP remain their separate issues.
