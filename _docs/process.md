- Tasks are GitHub issues, one at a time
- Read the acceptance criteria before starting and before closing
- Commit regularly

Roles

- PM - grooms a task before anyone implements it, follows _docs/team/pm.md
- Engineer - implements one groomed task, follows _docs/team/software-engineer.md
- QA - checks the result against the acceptance criteria, follows _docs/team/qa-engineer.md

Orchestrator

The main session is the orchestrator. It launches the PM, the engineer
and QA as subagents. It does not groom, implement or test itself.

Lifecycle

1. Pick the next open issue from the backlog
2. PM grooms it
3. Engineer implements it
4. QA verifies it
5. On FAIL, back to step 3 with the QA comment as input
6. On PASS, the orchestrator publishes the exact QA-approved commit
7. Independent QA verifies that exact commit is published, then closes the issue
8. Repeat until the backlog is empty

Rules

- Do not skip step 2
- The engineer does not close the issue
- QA does not fix the code, only outputs PASS or FAIL
- The orchestrator publishes the exact approved commit only after independent QA PASS
- Independent QA closes the issue only after confirming that exact approved commit is published; the engineer never closes

Backlog consolidation

When the user requests consolidation, PM proposes canonical packages and a
complete source-to-survivor mapping that preserves every source requirement.
The engineer updates backlog documentation without changing application work.
Independent QA audits scope coverage, canonical dependencies, completed history,
and preservation of local changes before any administrative closure.

After this audit passes, update surviving issue bodies first, then post explicit
replacement links and close only superseded issues with reason `not_planned`.
Those closures mean the separate records are superseded; they do not claim
implementation or implementation QA PASS. Verify final issue counts and mapping.
Surviving implementation packages still follow the lifecycle above and require
independent QA PASS and publication of the exact approved commit before independent QA completed closure. Keep one active package at a time;
packages may require multiple focused commits rather than one session.

Dependency authorization

The user has granted standing approval to add and install the minimal
dependencies required for agreed Student Marketplace backlog issues, including
their resolved dependencies. Document each dependency change in the issue's
implementation report and keep manifests and lockfiles updated. Earlier issue
boilerplate asking for dependency approval is satisfied by this authorization
for dependencies within that scope. Unresolved product choices still require
user input; the PM, engineer, and independent QA lifecycle remains unchanged.
