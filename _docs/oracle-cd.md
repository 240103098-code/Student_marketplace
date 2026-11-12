# Additional Oracle demo automation (#96)

Status: partial activation, not completed automatic deployment. After explicit
owner consent, the restricted deployment account/controller and encrypted
`oracle-demo` environment secrets were installed and independently inspected.
The first real main deployment passed CI but failed in the retained-state helper
before the intended health-drill pause. The previous application recovered;
the ordinary stop/recovery outage is not proof of the planned drill. See the
[observed loader bug and corrective work](evidence/oracle-98/README.md).

Initial preparation included27 focused policy/transaction regressions and five
Bash syntax checks. Its actual branch CI passed364 backend,166 frontend and two
Playwright tests, with deployment skipped. Corrective issue98 adds five tests
that execute the actual emitted retention program with real configuration and
guarded PostgreSQL; all32 focused tests passed locally. Candidate CI and the
reviewed installed-controller snapshot proof are still required for that fix.
Issue96 remains open pending its real pause/rollback and successful release.
Earlier issue97 completed independently before this work resumed.
Independent preliminary review found that private umask077 reduced extracted
source directory modes. Extraction now explicitly normalizes all descendant
directories to0755 while the release root remains0700; the Linux CI regression
checks actual POSIX modes and unchanged-source retry. Windows passing that case
is not proof of POSIX permissions.

## Reviewable access plan

Use a new Ed25519 key exclusively for this repository's Actions deployment job.
Store its private part in encrypted **environment** Actions secret
`ORACLE_DEMO_DEPLOY_KEY`, the existing host address in `ORACLE_DEMO_HOST`, and the
previously verified host-key line in `ORACLE_DEMO_KNOWN_HOSTS`, all within GitHub
environment `oracle-demo` in this repository. Configure selected deployment
branches to **branch main only**, with no tag rule, before storing these secrets.
[GitHub documents this capability for public repositories on all current plans](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
The reviewed workflow references the environment only in its dependent main job.
A writer who compromises an authorized main workflow could still reference that
environment's key, so the independent server-side gate and forced command remain
essential. No environment configuration, required reviewer or branch protection
is claimed until its actual settings are inspected. No paid feature is enabled. SMTP,
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

The bounded automation rejects any changed PostgreSQL/SQLite migration inventory
or Alembic configuration. Existing forward migration invocation remains in place,
but a future schema change requires a separately reviewed compatibility plan; an
image rollback is not a database downgrade. The controller also refuses less than
6GiB free disk, more than eight owned source releases/images, or twenty retained
backup directories. It never performs a global prune or deletes an old release
automatically. An operator must separately inspect ownership and preserve the
current/previous images, backups and all persistent volumes before manual cleanup.

The server-owned controller is not self-updated from future application commits.
An explicitly reviewed installation places it and fixed Compose/Caddy/backup
files under `/opt/student-marketplace-cd`. The root directory is0711 solely so
the dedicated account can traverse to its forced gateway; private configuration,
state and recovery snapshots are0600, private subdirectories0700. All relevant
ancestor directories must be root-owned and not writable by other identities.
Only the image reference changes in existing runtime configuration.

An exclusive lock serializes server operations. Before the first service stop,
the controller saves private config/previous release and arms a generation-bound
ten-minute systemd fallback. It snapshots canonical private row hashes and
relative image paths/bytes during the bounded maintenance window. A failed
deployment returns FAIL even after successful recovery. A delayed old timer
cannot roll back a later generation. Interrupted or failed timer arming leaves a
private pending record and rejects later deployment; the owner must inspect and
run the installed root recovery command for that exact generation, not delete
configuration or volumes. Backups remain on-host and are not independent disaster
recovery. Existing service limits/log rotation remain unchanged; build timeout is
30minutes and its Docker memory flag is not a claim of a separately isolated
host-wide build resource manager.

## Acceptance and limits

Before activation: independent safety review, focused controller/workflow tests,
then explicit approval naming the three GitHub secret destinations and restricted
access to the existing VM, including brief controlled demo downtime for the
health-failure drill below. After activation: inspect actual account/key/sudo
restrictions, observe a real approved main commit after complete CI, prove failed
CI cannot deploy, and exercise a controlled health failure with actual rollback.
Keep #96 open until those real outcomes and exact publication pass independent QA.

### Activation and actual proof sequence

1. Independently approve the exact local candidate, run actual full branch CI and
   verify its deployment job is skipped on the non-main branch. Obtain specific
   owner consent before creating the key, account, GitHub environment/secrets or
   host access rules. No private key belongs in a source bundle.
2. Prepare the reviewed public operations bundle and sanitized installation
   inputs under a root-owned private staging directory on the existing host.
   `ops/oracle/install-cd.sh BUNDLE NEW_PUBLIC_KEY CONFIG_JSON` accepts only a new
   Ed25519 public key and config fields `hostname` and verified numeric
   `workflow_id`. It records the actual already healthy application image/source,
   without restarting it, and installs restricted access. The script refuses
   existing account/home/controller targets. An early partial installation keeps
   its private audit directory for manual review; after account creation its
   failure trap removes the new key/sudo/sshd rules. Never blindly overwrite it.
3. Independently inspect effective sshd configuration, key restrictions, exact
   sudo command and permissions. Verify invalid commands, arbitrary shell,
   forwarding and extra controller arguments cannot run. Configure/inspect the
   main-only GitHub environment and encrypted secrets. Pin the existing verified
   host key; never trust a new unverified ssh-keyscan result.
4. Publish only an independently approved benign main commit. All required tests
   must pass for that exact SHA/attempt before the real deployment job can run.
   Observe the actual source label/image, public HTTPS and retained private state.
5. For the explicit controlled health-failure proof, the owner may write root600
   `/opt/student-marketplace-cd/health-drill.json` containing exactly
   `{"sha":"<approved full SHA>","generation":"<run>-<attempt>-<same SHA>"}`.
   This is an operator-only one-shot file, not an SSH request option or CI flag.
   The installed controller validates and atomically consumes it **before** pausing
   only the newly healthy, exact-image/project app container. A real trusted HTTPS
   readiness request must then fail. Immediate or timed recovery unpauses that
   exact owned container and recreates the previous verified image/config;
   retained hashes/paths must match and the deployment reports FAIL. This causes
   brief real demo unavailability; it is not a fabricated exception or app-code
   mutation. No email, credential rotation or schema change is part of the drill.
6. Rerun the **entire original push workflow**, including both prerequisite jobs,
   or use a new independently approved benign main commit. Rerunning only a failed
   deployment job deliberately fails the attempt-specific server gate. A failed
   source directory can be reused only after its complete file/type/content
   inventory matches a fresh canonical archive. Unknown or changed files are
   rejected; no blind reuse or recursive cleanup occurs. Observe final successful
   automatic deployment and independent public/state checks.
7. Preserve sanitized counts/results, source and image hashes, gate rejection,
   actual failed readiness and last-healthy restoration, final version and
   publication evidence. Never publish raw Docker/SSH output, private state or
   marker contents containing infrastructure inputs. Failed CI proof must use a
   separately reviewed deliberate-failure branch; do not merge its failing test.

This builds ARM from the checked source; it does not promote the exact x64 image
tested by CI. #87, full feature coverage, AWS/GCP, teacher acceptance and broad
production operations retain their separate requirements. Historical November 3
evidence is not represented as a fresh November 12 deployment.

To revoke access, remove the dedicated authorized key and its single sudo rule,
disable the deployment account, and delete the three GitHub secrets. Existing
running application/data need not be stopped. Rotate only this dedicated key
through the same explicit review/consent path; never expose it in logs/artifacts.
