# Actual registration E2E evidence — 2026-11-15

[Linux CI run 43714515394](https://github.com/240103098-code/Student_marketplace/actions/runs/43714515394) passed implemented checks and the required gate on runtime commit `02b39b22d784eb0652c7d6f32cdb9ed372b5c216`. Oracle deployment was skipped for this candidate branch. [Independent QA accepted the runtime result](https://github.com/240103098-code/Student_marketplace/issues/61#issuecomment-6894502137). This follow-up preserves reviewed safe evidence and documentation only; the executable, workflow, spec, helper, dependency and map bytes remain the tested inputs. Final main CI/CD and independent publication verification remain required before issue closure.

Artifact `14162830094` contained exactly the 18 safe files retained here. Its 21,656-byte ZIP SHA-256 is `17ed810aa3511c01a8001d9037f6ee31acc28f05b29bbbc58fea1a69a2e46fe9`. Archive membership and extracted bytes matched before copying. [Provenance](provenance.json) records each file hash and comparisons of 225 CI input hashes plus all four 12-input controller inventories with canonical Git blob bytes at the runtime commit. Windows checkout line endings are excluded from that comparison.

| Actual check | Result and evidence |
| --- | --- |
| Backend / frontend / build | [Summary](summary.json): 379 backend tests passed, zero skips; 166 frontend tests passed, zero pending/todo; typecheck, production build/mock exclusion, canonical OpenAPI and 40-operation map passed. |
| Real Compose | [Compose record](compose.json): readiness, migrations, persistence and failure gates passed. |
| Original default smoke | [Run](e2e-smoke-run.json) / [tests](e2e-smoke-tests.json): student and admin passed, browser exit 0. |
| Complete suite | [Run](e2e-run.json) / [tests](e2e-tests.json): registration plus both smoke tests passed, browser exit 0. |
| Registration-only | [Run](e2e-registration-only-run.json) / [tests](e2e-registration-only-tests.json): one registration test passed, browser exit 0. |
| Registration behavior | [Full stages](e2e-registration-stages.json) / [isolated stages](e2e-registration-only-registration-stages.json): all six stages completed in each run, four POSTs (201 twice, 409, 503), controlled SMTP success/failure observed, zero external browser requests, 390px viewport. |
| Original intentional failure | [Run](e2e-intentional-failure-run.json) / [actual tests](e2e-intentional-failure-tests.json): student failed with browser exit 1 after the [complete predecessor journey](e2e-intentional-failure-student-stages.json) and controlled-failure stage. Admin never ran after maxFailures=1; no pass/skip row is invented. Controller PASS means this expected failure and cleanup were correctly recognized. |
| Isolation and cleanup | All four child stacks removed owned containers/networks/volumes and private files; the borrowed image was preserved until the parent removed its owned shared image and guarded PostgreSQL resources. Parent cleanup passed. |

One image was built: `sha256:bff8ae3d4d1bd0f13b0b97c8926d2b91700b8137e1ce24098a7dc05cbda1ab70`. Every Compose/Playwright borrower used that exact identity and fresh database/uploads/SMTP/limiter state. Python 3.13.15; Node v24.19.0; npm 12.2.0; Docker 28.0.4; Compose 2.38.2; PostgreSQL 18.6; Playwright 1.62.1; Chromium/headless-shell revision 1234, browser 151.0.7922.34. Reproduce the four fixed modes with the commands in [CI](../../ci.md) and [E2E](../../e2e.md).

The feature covers normalized 12-character-password signup and durable unverified student/code state, duplicate preservation, invalid university-domain/password rejection, actual authenticated STARTTLS delivery failure/rollback/restored retry with a 128-character password, private response/page/URL/storage checks, anonymous denial, keyboard focus/submission and mobile layout. Browser UI performs registrations; helpers expose only fixed scoped read-only state predicates. Only POST /auth/register gains feature coverage. No application behavior, runtime dependency or external email provider is changed or claimed complete.

Earlier failed runs are retained as history, not relabeled:

| Runtime candidate / actual run | Observed result and correction |
| --- | --- |
| `37227504d9ded92e6855ba787eca1271b5d0de2c` / [43711409870](https://github.com/240103098-code/Student_marketplace/actions/runs/43711409870) | Registration timed out in duplicate-preserved after 201/409; coarse diagnostics could not identify the wait. Cleanup passed. |
| `c454acb1156eb9c9822998c34e4b620f33535d72` / [43712506676](https://github.com/240103098-code/Student_marketplace/actions/runs/43712506676) | Fixed safe timings proved success completed at 1585ms and duplicate feedback/state/mail checks at 2324ms; Playwright inspector response.text then hung until the unchanged 90-second deadline. Passive cloning of the actual native fetch response replaced that observation boundary without dropping body privacy checks. Cleanup passed. |
| `680f863449f4b3167a95b1fc7f871fa1ff8f29e4` / [43713622731](https://github.com/240103098-code/Student_marketplace/actions/runs/43713622731) | All feature modes passed and expected browser failure was recognized by its child. Parent gate wrongly required an end record for unexecuted admin. The final candidate corrects only that intentional-mode record policy; normal modes stay strict. Cleanup passed. |

The only PNG is a fully solid masked [intentional-failure viewport](e2e-intentional-failure-student-masked.png). Preserved JSON contains fixed logical labels, times/counts/statuses, versions, input/image hashes and cleanup predicates. No raw response bodies, database rows, accounts, passwords, hashes/codes/tokens, native reports/logs, traces/HAR/video/storage state, inboxes, secrets or keys are preserved. Provider inbox delivery and other feature issues remain separate. No main publication, deployment or completed closure is claimed by this evidence commit.
