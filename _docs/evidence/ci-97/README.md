# Issue97 diagnostic evidence

## Actual unchanged-parent observations

Parent source: `b5dc1ec9643ea1cf2e346f31dd6d2776ecdaa594`.

- [Actual main attempt1](https://github.com/240103098-code/Student_marketplace/actions/runs/43212254097/attempts/1)
  failed before backend discovery. Artifact13941707326 ZIP SHA256
  `63e75e946aef75ad5347da0ce05abcbf874a9b32528f45c7016696e8d04fc820`.
  [Byte-preserved safe summary](parent-attempt1-summary.json) records no completed
  checks, broad prerequisite failure and successful cleanup; no exact operation.
- [Bounded retry, attempt2](https://github.com/240103098-code/Student_marketplace/actions/runs/43212254097/attempts/2)
  passed without source changes:325 backend/zero skips,166 frontend and2 real
  Playwright tests,9 completed checks, one shared image, owned cleanuptrue.
  Artifact13942591165 ZIP SHA256
  `c764f96957c4fd352daa258213aca12a9a010d323380cf9643d12685f1f8eee6`.
  [Byte-preserved safe summary](parent-attempt2-summary.json).

The initial registry/Docker/command cause remains unknown. These observations
justify a diagnostic repair, not an assertion that application tests failed or
that the underlying infrastructure cause was fixed.

## Deterministic parent/candidate comparison

[Measured comparison](parent-candidate-comparison.json) executed the unchanged
parent controller from its Git blob and the candidate controller in separate
temporary output roots. Docker/tool inspection was stubbed; the same container
start position executed a **real harmless Python subprocess exiting37** with
private synthetic stdout/stderr sentinels. This is an intentionally controlled
failure, not a reproduction of the unknown real infrastructure cause.

Both returned FAIL and completed owned cleanup. Parent exposed only
`prerequisites/subprocess-status`; candidate exposed
`postgres-container-start/exit-status/37` with timeoutfalse. Public summaries and
captured console contained neither native sentinel. The reproduction used the
ignored local operator harness, not a public workflow failure switch.

Candidate focused commands:12 new diagnostic regressions plus2 existing CI gate
regressions passed on Python3.13.15. Initial Windows execution hit a sandbox TEMP
permission error before the controller case; rerunning with workspace-owned
TMP/TEMP executed all cases successfully. No checks were skipped. Actual candidate
full CI is pending; this checkpoint does not close97 or claim full-suite success.

Only already allowlisted sanitized JSON and this report are preserved. Native
logs, argv/environment, identities, SMTP state, keys and raw fixture artifacts
are absent. No Oracle CD draft files are part of issue97.
