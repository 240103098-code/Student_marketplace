# Actual #60 verification evidence — 2026-11-03

[GitHub Actions run 41579933950](https://github.com/240103098-code/Student_marketplace/actions/runs/41579933950) completed successfully from 04:45:14 to 04:47:15 UTC on GitHub-hosted Ubuntu 24.04. The tested runtime commit is `84a76ce6895770f41350c93a11e64fefcd9dbbff`. This evidence/documentation follow-up changes no runtime, test, workflow, dependency or map inputs and requires no repeated stack run.

The downloaded allowlisted artifact is ID `13204434678`, SHA-256 `75d50c01046c1d4a47119752eb5865dadb4db957da1c30555bd2610e1301ac33` (4,083 bytes). The archive hash matched GitHub's recorded digest before its safe fixed-name JSON/PNG members were extracted. [Provenance](provenance.json) records the run, exact runtime candidate, artifact/file hashes and targeted local regression results. Each runtime input hash in both run records was independently compared with that candidate's canonical Git blob bytes and matched; Windows checkout line-ending conversion is not mistaken for a source change.

The actual commands were `npm ci --prefix e2e --ignore-scripts --no-audit --no-fund`, matching Playwright Chromium installation, `python3 tools/e2e_stack.py`, then `python3 tools/e2e_stack.py --intentional-failure` after preserving the first safe directory. The workflow file at the tested commit defines the exact installation and command arguments.

| Evidence | Actual outcome |
| --- | --- |
| [Positive run](e2e-positive/run.json) / [tests](e2e-positive/tests.json) | Playwright exit 0; 2 of 2 tests passed |
| [Student stages](e2e-positive/student-stages.json) | Real UI signup, actual authenticated STARTTLS mail, UI code verification/login, protected reload, fresh-context API/UI denial; 14 actual API responses; 0 external browser requests |
| [Admin stages](e2e-positive/admin-stages.json) | Separate normal UI signup/mail/verification, existing operator admin CLI, UI login/current admin access; 13 actual API responses; 0 external browser requests |
| [Intentional run](e2e-safe/run.json) / [tests](e2e-safe/tests.json) | Playwright exit 1 and student test failed, intentionally; second admin test not run after maxFailures=1 |
| [Failure stages](e2e-safe/student-stages.json) | All six prior stages completed; deliberate final assertion began and did not complete; 14 actual API responses and validated real SMTP |
| Cleanup, both independent runs | Project containers/volumes/networks absent, owned image absent, private temporary files removed; controller PASS means the expected browser outcome and cleanup both passed |
| [Masked failure screenshot](e2e-safe/student-masked.png) | Whole HTML document visibly masked; 1280×720 viewport, no account/code/password/page text |

Docker 28.0.4; Compose 2.38.2; PostgreSQL 18.6; Node v24.19.0; npm 11.17.0; `@playwright/test` 1.62.1; matching Chromium and headless-shell revision 1234; actual browser 151.0.7922.34. The production image's existing frontend builder npm version remains unchanged. Both independent runs used image ID `sha256:8a94d6991c01720ca44ed78adf07bc8341db77d5d1fec3ad820a0a5bd6e9ff85` and fresh generated storage/app state.

Targeted harness/Compose regressions: 10 passed, no skips; engineer 8.833 seconds and independent QA 9.115 seconds outside the Windows native sandbox. That includes the normal runtime `SmtpSender` over actual trusted STARTTLS, untrusted CA rejection, wrong authentication and external-recipient rejection, safe reporter secret suppression, project-ownership refusal, parallel-override refusal and bounded/sanitized subprocess failures. The complete guarded PostgreSQL regression suite is not claimed by these targeted results.

The JSON retains logical stages, success/failure statuses, counts and version/hash evidence only. No native Playwright/Docker/OpenSSL output, traces, HAR, videos, storageState, error-context, inbox, generated secrets or credentials were downloaded or preserved. The source artifact remains under its seven-day GitHub retention; these reviewed safe members are durable repository evidence. No feature issue #61–#85 acceptance or closure is claimed. Only independent QA may approve the final exact commit and close #60 after root publication is confirmed.
