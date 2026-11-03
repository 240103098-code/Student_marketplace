# Additional Oracle HTTPS demonstration (#95)

This is a bounded additional demonstration on the user's existing ARM host. It
does not implement AWS CloudFormation/GCP Terraform (#89), establish teacher
acceptance (#56), certify high availability, or complete operations (#90).
Resource sizing alone is not proof of zero billing. No new cloud resources,
subscription upgrades, additional disks, reserved addresses or purchased domains
are authorized by this procedure.

## Source and private boundaries

The application release is the independently verified main commit
`c3869077ef70d1c2bfdc14f6aa87daa25108bbbb`. Build only a clean `git archive` of
that commit, plus the separately identified reviewed operations files. Verify
both archive hashes before extraction. Keep source root-owned under
`/opt/student-marketplace-demo/releases/<application-SHA>` with a `current`
symlink. Record full application and operations commit IDs separately in
`RELEASE-SHA` and `OPS-SHA`. An operations commit is not a different application
release. Never build an old clone or copy an old private configuration/database.

Runtime configuration belongs in root-owned mode0700
`/etc/student-marketplace-demo`, with mode0600 regular nonsymlink files.
`prepare-runtime.py` generates a fresh strong database password and stable JWT
secret there, refuses existing configuration, and never prints values. Preserve
these files across restarts. The Docker build whitelist excludes operations,
environment files, keys and private data; secrets are never build arguments.

SMTP is optional until explicitly configured from the user-designated private
source. No default account, administrator seed, code endpoint, mail fixture,
test mode or verification bypass is installed. User inbox access is not part of
deployment authorization. Never include sender/recipient identities, codes,
passwords, cookies, tokens, expanded Compose configuration or raw logs in evidence.

## Reviewed host preparation

The selected host was freshly reconfirmed as aarch64, 1OCPU/6GB, 45GB root disk
with approximately43GB free, Ubuntu20.04.6 and no Docker/application data. The
user explicitly authorized its in-place20.04→22.04 LTS upgrade and reboot.
Ubuntu20.04 is outside standard maintenance and is not the deployment runtime.

`upgrade-to-jammy.sh prepare` preserves SSH, netplan, apt configuration, firewall
rules and package inventory under root-private `/root/marketplace-os-upgrade`,
updates Focal, and stops. Reboot separately if `/var/run/reboot-required` exists.
Only then run its `release` phase. Both phases run as detached systemd services;
monitoring is bounded without forcibly killing dpkg mid-transition. The official
release upgrader's noninteractive conffile handler retains current configuration.
Oracle agent services are temporarily stopped to avoid package-lock conflicts,
with an exit trap restoring them. No development-release flag or manual codename
substitution is used.

Before the final reboot require successful service exit, the explicit ready
marker, valid `sshd -t`, clean `dpkg --audit`, and validated persistent firewall
files. The upgrade switched the iptables alternatives to nft while the original
live rules remained legacy; independent preliminary QA approved restoring both
alternatives to legacy without flushing/restoring live rules, then rebooting.
Reconfirm SSH with the existing pinned host key, new OS/kernel, agents, firewall,
disk and failed-service state after reboot. If SSH fails, use the owner's Oracle
console recovery; do not reimage or create replacement paid resources.

`enable-https-ports.sh` adds only NEW TCP80/443 INPUT rules and persists them using
the existing framework **before Docker starts**. This excludes dynamic Docker
chains from saved host rules. Existing SSH and Oracle InstanceServices rules stay
in place. Docker-published ports bypass INPUT; the deployment protects internal
services by publishing only proxy80/443. Inspect Docker's FORWARD/DOCKER-USER
rules and actual mappings as well as the host INPUT chain.

`install-docker.sh` requires Jammy/arm64 and no conflicting packages. It downloads
the official key, checks fingerprint
`9DC858229FC7DD38854AE2D88D81803C0EBFCD88`, and uses the signed Jammy stable apt
repository. Its first run records exact candidates and exits for review; the
second installs that same allowlisted version list. Docker administration stays
root-only; no broad Docker group grant or convenience installer is used.

## Runtime

`inspect-images.py` checks official Docker Hub index bytes against the registry
digest and required pinned digest, then requires a native linux/arm64 manifest.
Do this before pulling/building every Node/Python/PostgreSQL/Caddy base image.
Never silently substitute an image or enable emulation.

Build the actual application with `--platform linux/arm64`, its exact SHA tag
and `org.opencontainers.image.revision` label. Inspect the resulting image's
architecture, revision and RepoDigests. Before first startup, replace only
`MARKETPLACE_IMAGE` in the root-private runtime file with the resulting local
`student-marketplace-demo@sha256:<actual-index-digest>` reference, retaining
mode0600 and all generated secrets. The initial SHA tag is a build locator;
the running services must use the inspected digest. Do not edit a saved database
password or JWT key when pinning the image. Run the base `compose.yaml` plus
`ops/oracle/compose.https.yaml` through the root-only `demo-compose.sh` wrapper.
Validate configuration with `config --quiet`, never a secret-expanded dump.
The override retains the original migration/upload initializer gates, nonroot
read-only app and PG18 `/var/lib/postgresql` volume, removes the app host mapping,
and adds only Caddy TCP80/443. PostgreSQL and private uploads remain named volumes.
Caddy certificate/account/config state persists in its own named volumes.

Caddy uses automatic ACME publicly trusted TLS with automatic renewal and HTTP
redirects. The free IP-derived hostname is recorded privately for the owner;
verify that its actual DNS A record matches the selected host before issuance.
There is no browser certificate bypass. If cloud ingress is blocked, the owner
adds stateless-disabled TCP ingress80 and443 from0.0.0.0/0 to the selected subnet
security list or attached NSG, preserving SSH22. No cloud API credentials are
needed or read. Add IPv6 ingress only if that host actually has public IPv6.

The app/migration limit is768MiB, DB1GiB, proxy256MiB and upload initializer256MiB;
per-service CPU/pid caps bound this1OCPU demo. Each service rotates three10MB
Docker log files. Caddy request-access logging is disabled. These are basic
capacity safeguards, not production sizing or high availability.

## Backup, reboot, stop and rollback

Stop app/proxy for an aligned maintenance backup:

```sh
sudo /opt/student-marketplace-demo/current/ops/oracle/demo-compose.sh stop app proxy
sudo /opt/student-marketplace-demo/current/ops/oracle/backup.sh
sudo /opt/student-marketplace-demo/current/ops/oracle/demo-compose.sh up -d --no-build
```

The backup requires existing owned volumes, creates a custom PG dump plus private
uploads archive, preserves stable runtime secrets and release/image provenance,
and hashes the data artifacts under root-only
`/var/backups/student-marketplace-demo/<UTC>`. It refuses below4GB free or after20
backup directories. It never deletes older backups automatically. Retain an
independent encrypted copy separately; a backup on the same VM does not survive
loss of that VM/disk. Certificate state also needs protection if migrating hosts.

Run `verify-backup.sh /var/backups/student-marketplace-demo/<UTC>` to restore the
dump and images in uniquely named disposable volumes without public ports or
network access. It validates the migration head, tables and every restored image
byte hash and removes only its own temporary resources. An empty initial backup
does not prove retention of later uploaded images. Repeat with actual authorized
synthetic account/image data before claiming recovery verification.

An authorized host reboot must be followed by outside-VM trusted HTTPS readiness,
actual session refresh/login and byte-identical own-image checks. Restart policies
and volume names must remain stable. `demo-compose.sh stop` stops only the demo;
`down` retains volumes. Do not use `down -v`, global prune or cloud teardown.

Before a future update, preserve the prior reviewed image ID, operations files,
runtime file and backup. Rollback selects the previous verified image/config
with the same project and volumes and uses `up -d --no-build`; validate schema
compatibility first. Never run a destructive migration downgrade or remove
volumes to make rollback pass. A first deployment has no previous application
release to roll back to; stopping the owned demo is its safe initial fallback.
For this demonstration, a genuine published historical995 commit was first
deployed and independently verified **now** as a new drill baseline, followed by
995→currentc386→actual995 rollback→finalc386. Its application input trees are
identical to current, so this tests digest/config selection and retention, not
different binary/schema compatibility or earlier production history. See the
[measured drill and exact hashes](evidence/oracle-95/verification.md).

The reviewed one-time `rollback-drill.sh` prepares private snapshots, serializes
phases/recovery with flock, and uses app-only recreation with health deadlines,
error recovery and a20minute automatic fallback. Independent outside verification
gates each phase. The successful final-current stage cancels the fallback timer.
It refuses to overwrite an existing snapshot directory; another drill requires
separate review. No schema downgrade or volume deletion is part of the drill.
Unexecuted future rollback scenarios remain unverified.

## Normal mail and privacy verification

`public-flow.py` is a separate operator harness, never application startup.
Its private identity/session/cookie/code files stay owner-only and ignored.
With an explicitly authorized real university recipient, register sends only
through normal HTTPS registration/SMTP, pre-incrementing a maximum-three message
budget before network I/O. The user reads their own inbox and supplies the code
privately. Finish uses normal verification/login, uploads a generated nonsensitive
PNG, verifies production cookie attributes, own protected reads, anonymous denial,
public-upload denial, bad-origin rejection and real CSRF/refresh. Check refreshes
the retained session before testing the image hash after reboot/replacement.
One authorized account proves own-route and anonymous privacy behavior; it does
not prove cross-account ownership isolation on this public instance.

Actual outcomes and limitations must be recorded in the sanitized #95 evidence.
Preparation and preliminary safety PASS do not constitute final deployment QA.

Official references: [Ubuntu on Oracle upgrade guide](https://ubuntu.com/docs/oracle/oracle-how-to/upgrade-from-focal-to-jammy/),
[Docker supported Ubuntu installation and firewall behavior](https://docs.docker.com/engine/install/ubuntu/),
[Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).
