# Additional Oracle demo automation (#96)

Status: preparation only. No deployment key, GitHub secret, account, sudo rule or
host controller has been created or installed by this change. Activation requires
the owner's explicit approval of the access plan below and independent safety
review. Do not describe this as completed automatic deployment until measured.

Draft checkpoint: code is unexecuted and incomplete. Do not install or publish
this branch as working automation. Independent fallback recovery, installation
and revocation tooling, focused regressions and actual activation/CI/rollback
evidence remain to be completed. Work paused to diagnose the existing main CI
prerequisite failure under #97; no successful #96 test result is claimed.

## Reviewable access plan

Use a new Ed25519 key exclusively for this repository's Actions deployment job.
Store its private part in encrypted repository Actions secret
`ORACLE_DEMO_DEPLOY_KEY`, the existing host address in `ORACLE_DEMO_HOST`, and the
previously verified host-key line in `ORACLE_DEMO_KNOWN_HOSTS`. The reviewed
workflow references these secrets only in its dependent canonical-main job;
repository secrets themselves are not restricted to that job by GitHub. A writer
who changes an authorized workflow could reference the key, so the independent
server-side gate and forced command remain essential. Environment approvals and
branch protections are not configured or claimed by this proposal. SMTP,
JWT, database secrets and the owner's administrative key never enter GitHub.

The public key belongs to dedicated account `marketplace-deploy`, with a
root-owned home and authorized_keys. Its key options use `restrict` and a fixed
forced command. No password login, forwarding, PTY, agent/X11 forwarding,
Docker group membership or general sudo is granted. A fixed root-owned gateway
passes the SSH original command through stdin to one no-argument privileged
controller. The sudoers exception allows that controller only, with no arguments.
The controller accepts exactly `deploy <40 lowercase hex SHA> <run id> <attempt>`.
Anything else fails closed; no shell interpolation evaluates request content.

The controller independently reads public GitHub API metadata for the canonical
repository and installed workflow identity. It requires a push/main run at that
SHA and attempt and successful `CI / implemented checks` and `CI / required gate`
jobs. The enclosing workflow is still running during its deployment job, so its
overall completion is not used as a substitute for prerequisite job results.
Network errors, missing data and rate limits reject deployment. It then verifies
the exact current main SHA and ancestry from the last successful release, under
a host-exclusive lock. Actions also serializes deployments without cancelling an
in-progress release. An older queued run cannot replace newer main.

Only canonical public source is fetched into owned releases. Host execution uses
the separately installed root-owned controller and fixed reviewed Compose files,
not scripts or Compose configuration from the fetched candidate. Native ARM Docker
builds receive no secrets, host mounts or Docker socket. Migrations run inside the
nonroot candidate application container. Existing private runtime/SMTP files,
database/uploads/proxy volumes, HTTPS settings and resource limits are preserved.

Record the previous image/config before activation. Bound all subprocesses and
health checks, preserve a private backup, run only forward migrations, verify
trusted HTTPS readiness/static content and persistent state, and mark current
only after success. Failed activation restores the previous image/config; schema
downgrade, volume deletion, secret rotation and global prune are forbidden.

## Acceptance and limits

Before activation: independent safety review, focused controller/workflow tests,
then explicit approval naming the three GitHub secret destinations and restricted
access to the existing VM. After activation: inspect actual account/key/sudo
restrictions, observe a real approved main commit after complete CI, prove failed
CI cannot deploy, and exercise a controlled health failure with actual rollback.
Keep #96 open until those real outcomes and exact publication pass independent QA.

This builds ARM from the checked source; it does not promote the exact x64 image
tested by CI. #87, full feature coverage, AWS/GCP, teacher acceptance and broad
production operations retain their separate requirements. Historical November 3
evidence is not represented as a fresh November 12 deployment.

To revoke access, remove the dedicated authorized key and its single sudo rule,
disable the deployment account, and delete the three GitHub secrets. Existing
running application/data need not be stopped. Rotate only this dedicated key
through the same explicit review/consent path; never expose it in logs/artifacts.
