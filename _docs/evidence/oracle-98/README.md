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
Independent QA reran all32 tests against the owned disposable loopback database,
with zero failures, errors or skips. An interrupted owned local test cluster
required recovery; only that cluster was restarted and its old log moved outside the data
directory. The user's separate database was not touched.

Actual [code-candidate CI43491464475](https://github.com/240103098-code/Student_marketplace/actions/runs/43491464475)
passed for `7320cf4c96b03c67388932ba502d4c34f04a1fbd`:369 backend tests,
166 frontend tests and two real Compose Playwright tests, with zero skips and
successful required gate/owned-resource cleanup. All nine implemented checks
passed; the Compose and Playwright chains shared one built image. Deployment was
correctly skipped on the non-main branch.
[The bounded CI record](code-candidate-ci.json) identifies the exact source,
artifact digest and actual counts. It does not claim CI for a later documentation
commit; final exact-candidate CI and publication are verified separately in
[issue98](https://github.com/240103098-code/Student_marketplace/issues/98).

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

## Actual installed correction and independent snapshot

After the code-candidate CI and independent safety approval, the reviewed
controller-only update completed under the existing deployment lock. The original
file was preserved privately and the installed root600 controller now has the
canonical code-candidate Git-blob SHA256
`3dfd1d0ddb5570453f6431edbd9e8cab27e811886efd595ae21f1727ac2b48aa`.
The [update record](controller-update.json) faithfully transcribes the actual
operator result; it is explicitly not claimed to be a byte copy of an original
log file. State/runtime configuration stayed unchanged and the original
application remained healthy. No access installer or credential setup was rerun.

Independent QA then executed the installed `Host.retained()` twice against the
actual configured, nonempty application at `2026-11-13T19:30:48Z`
(November14 in the user's timezone). All seven complete table hashes and the
relative-path/byte hashes of one uploaded file agreed. The account table was
nonempty; no rows, object paths, settings or private hashes are published.
The [sanitized independent measurement](installed-snapshot.json) preserves the
measured fields. It also confirms the original application source
`c3869077ef70d1c2bfdc14f6aa87daa25108bbbb`, image/container and four persistent
volumes match the pre-update baseline, readiness remains successful and runtime
and SMTP configuration are unchanged. These reads used no authenticated
requests, email or application-data writes.

This is an actual installed snapshot-loader correction, not an automatic release
of a new application image. The original failed deployment and the forthcoming
corrected deployment remain distinct observations.

The remaining issue96 drill requires a fresh source/generation marker under the
existing owner authorization. The failed original attempt must never be relabeled
as that intended proof. Exact CI-tested image promotion, full feature E2E, provider
acceptance and AWS/GCP remain their separate issues.
