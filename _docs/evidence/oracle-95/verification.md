# Oracle demo #95: measured evidence, 2026-11-03

Current result is **PARTIAL pending final acceptance**. Public HTTPS, real
mail/user-code verification, normal protected API/UI login, nonempty backup and
isolated restore, and runtime reboot/session/image retention have passed.
An executed prior-release rollback is unavailable on this first installation and
is not claimed. #95 stays open until final acceptance review and exact independent
publication verification. No AWS/GCP or teacher-acceptance claim is made.

## Provenance

| Item | Actual value |
| --- | --- |
| Independently verified application main | `c3869077ef70d1c2bfdc14f6aa87daa25108bbbb` |
| Deployed operations snapshot | `4b2650a1cb8e61eaf12096fb7904c27a0cd678a8` |
| Clean application git-archive SHA256 | `a600679097ac6eec460f312b62a187ba35364e4dc9d21bf2e42b710fbb82415c` |
| Operations-only git-archive SHA256 | `f4343feaf4dd08b2d5ff62e03c38f8a1904280cd7fe479e0020dec95b177f1d7` |
| Locally built native ARM image/index digest | `sha256:d13ce798cd83f4dd37b3631d17e85f5a7de8f431d930f1a5e9b4c13133f05cd2` |
| Application ARM manifest | `sha256:d297f250c1e69cb9be4382ba07c159c2888e38366308076275942b874d701847` |
| Application configuration digest | `sha256:c63af0e6de26a7c4dbcd7b906d09c6826546c2ef5119af48e7ebd8080e9dea3b` |

The actual app image is arm64 and its OCI revision label matches the full
application commit. Runtime selects its digest, not a mutable tag. Base Node,
Python, PG and Caddy index digests and native ARM child manifests are recorded in
[images.json](images.json), obtained from official Docker Hub with computed-byte
SHA256/header/pin equality. Caddy is2.11.7-alpine; PostgreSQL is18.6-bookworm.
The source/operations archives were independently regenerated and byte-compared
by QA, then hash-checked again on the host. No private configuration, ignored
data, keys or identity files were in either archive/build context.

## Host and supported runtime

The authorized existing A1 ARM host was privately reconfirmed with1OCPU/6GB and a
45GB root filesystem (approximately43GB initially free). User private evidence
showed the Free Trial console and an Always Free-only resource choice; shape and
capacity fit are not an account-wide usage/billing audit or zero-cost guarantee.
The agent created no cloud resources or paid plan/disk/address/domain upgrades.
The older unrelated host was not used.

Explicitly authorized Ubuntu20.04.6→22.04.5 LTS upgrade completed, followed by a
successful pinned-host-key SSH reconnect and kernel6.8.0-1062-oracle. Root-private
SSH/netplan/apt/firewall/package backups preceded the upgrade. The first release
metadata attempt safely refused before package changes; one identical retry
retrieved the official signed Jammy upgrader and completed. No development flag,
manual distribution-source substitution, reimage or paid support was used.

During the upgrade the default firewall alternatives changed to nft while the
old live rules remained legacy. Independent preliminary QA approved preserving
the original legacy backend without flushing live rules. Saved rules passed
restore syntax tests before reboot. After reboot SSH, netfilter persistence and
Oracle agents were active and there were zero failed units, including resolution
of transient mixed-version upgrade failures.

Official signed Jammy/arm64 Docker packages were recorded, independently reviewed
and installed at these exact versions:

```text
docker-ce=5:29.9.2-1~ubuntu.22.04~jammy
docker-ce-cli=5:29.9.2-1~ubuntu.22.04~jammy
containerd.io=2.4.2-3~ubuntu.22.04~jammy
docker-buildx-plugin=0.38.1-1~ubuntu.22.04~jammy
docker-compose-plugin=5.7.0-1~ubuntu.22.04~jammy
```

Actual Docker29.9.2 reports arm64; Compose5.7.0 validates the merged configuration,
including the app `!reset []` host-port removal. No application dependency changed.
All six new shell scripts pass Bash syntax validation; the three Python utilities
compile. These static checks supplement actual execution, not substitute for it.

## Actual deployment and independent outside checks

Migration and upload initialization exited0. The real PostgreSQL and application
services are healthy, with migration head `0003_listings`. App UID/GID are10001.
Actual root-private configuration directory/file modes are0700/0600; secrets were
generated outside source and retained during the app digest pin. Proxy `/data`
and `/config` are writable named volumes. The PG18 volume uses
`/var/lib/postgresql`; uploads use a separate owned private named volume.

Only Caddy TCP80/443 are published. Database5432 and app8000 have no host mapping.
Minimal NEW TCP80/443 host rules were added/persisted before Docker, preserving
SSH and original rules. Docker's FORWARD policy is DROP with DOCKER-USER and
DOCKER-FORWARD before the retained Oracle reject rule; INPUT alone is not claimed
to filter published container traffic. The owner reported separately adding cloud ingress.
Existing unrelated rpcbind was preserved rather than silently changed.

Offline Caddy validation initially failed because the validation command omitted
the already-reviewed proxy NET_BIND_SERVICE bounding capability. The same minimal
capability was added to that validation invocation; validation then passed with
network disabled, read-only filesystem and ephemeral state. No extra capability
was added to the deployed proxy. An initial Windows Schannel request failed
during startup; subsequent independent standard trusted TLS checks passed
without certificate bypass.

Independent QA results:

- [Public browser verification](qa-public-ui.json): six real Chromium151/Playwright1.62.1 checks passed, zero JS errors and zero external page requests; real React login/registration screens, mobile390px without overflow and protected-route sign-in behavior.
- [Public TLS/network verification](qa-public-network.json): trusted hostname TLS1.3, Let's Encrypt certificate expiring2027-02-01, actual HTTP→HTTPS redirect, liveness/readiness200, no-store/HSTS, unauthenticated auth/avatar401 and uploads404.
- Outside TCP22/80/443 reachable,5432/8000 unavailable. This is a bounded selected-port check, not a full port-scan/security certification.
- [Desktop](qa-login-desktop.png) and [mobile](qa-login-mobile.png) screenshots show blank public login fields with no identity or browser address bar.
- [Independent authenticated UI](qa-authenticated-ui.json): five actual postboot Chromium checks passed after explicit user authorization: normal UI login to protected Marketplace, production cookie flags/path, reload through real refresh, private avatar blob rendering with matching bytes, and fresh-context avatar401; zero JS errors or external requests. No authenticated screenshot or identity was exported.
- [Independent postboot public checks](qa-postboot-public.json): five public health/guard checks passed after automatic service recovery.

Measured app memory was approximately79MiB of768MiB, DB36MiB of1GiB, proxy10MiB
of256MiB, with approximately40GB disk free after build/deployment. Actual CPU caps
are0.75/0.50/0.25 respectively, PID caps128/128/64. Actual json-file log rotation
is three10MB files per service. These are measured basic safeguards, not load,
high availability or disaster-recovery certification.

## Normal mail, data and recovery

The user designated one private Gmail SMTP source and one own university
recipient, authorizing at most three verification messages. Neither identity is
included here. The private template was validated against six allowed fields and
provisioned only through encrypted SSH stdin into a root-owned0600 file, with no
secret CLI argument or output. No inbox access or test SMTP service was used.

The first normal HTTPS registration attempt returned503. Its attempt budget was
conservatively incremented before network I/O; it was not automatically retried.
The normal application transaction rolled back: actual counts were users0,
listings0, listing_photos0. No-send diagnostics passed greeting, EHLO and trusted
STARTTLS, then failed at AUTH with SMTPServerDisconnected. The owner supplied a
new sender/App Password privately; only FROM was aligned to that explicitly
provided sender under authorization. The root-owned SMTP file was atomically
rotated, and only the same pinned app container was recreated, preserving DB,
uploads and JWT configuration. A no-send verified STARTTLS/AUTH probe then passed.

The second conservative attempt returned201 through normal HTTPS registration;
the successful response was observed before the clock reading06:41:08UTC. The
user received that real message and supplied its fresh code in the protected
file. Normal verification/login returned200 without any DB/code bypass. The
operator uploaded a generated nonsensitive16×16PNG and verified actual protected
reads, private/no-store, byte hash, Secure/HttpOnly/Lax cookie with `/api/auth`
path, anonymous401, public uploads404, bad-origin403 and real CSRF/refresh200.
The consumed code file was cleared; tokens/passwords/cookies remain private.
Conservative attempts total2 of maximum3, with one successful verification mail;
no extra test email or resend was sent. Actual inbox arrival is established by
the user-supplied valid code, not merely SMTP acceptance.

A maintenance stop with restart trap produced a root-private PG custom dump,
uploads archive, stable-secret copies and release/image metadata. Isolated
no-network restoration passed exact `0003_listings` and user/listing/photo count
comparisons. Restored upload files were0. Owned temporary restore resources were
removed; public trusted HTTPS readiness200 returned after service restart.
This first run proved empty-state restore only. After the real account/image
flow, a second aligned backup and isolated restore passed: expected migration
head and account/listing/photo counts matched, actual users1 and avatar owners1,
and restored upload files1 with byte hashes compared to the archive. Temporary
owned restore targets were removed. Existing real-session refresh and private
image hash passed again after stop/start; no new email was needed.

Before the authorized runtime reboot, Docker/netfilter/SSH were active+enabled,
saved host rules validated and contained no Docker chains, SSH configuration was
valid, disk had approximately40GB free and there were zero failed units. The
runtime file hash was saved root-privately. After reboot at06:46:54UTC, pinned SSH
reconnected, all three persistent services recovered automatically without a
Compose repair, agents/firewall were healthy and the runtime file hash was
unchanged. Outside trusted HTTPS readiness returned200. The retained real
refresh session still authorized `/auth/me` and byte-identical private image
reads; public denials and origin/CSRF checks still passed. Independent QA then
passed public checks and normal authenticated browser login/avatar rendering.
See [sanitized measured operator results](operator-flow.json) for statuses and
the synthetic-image hash. No second account was authorized, so cross-account
ownership isolation on this public instance was not exercised; own-route and
anonymous privacy behavior were exercised.

The first installation has no previous application release to roll back to.
Stop/retain-data fallback and future image/config rollback commands are documented
in [operations](../../oracle-demo.md); a prior-release rollback was not executed
and is not reported as PASS. Backups on the same host are not independent disaster
recovery. Automatic certificate renewal is configured and certificate state
persists; a future time-based renewal has not yet occurred.

Actual hostnames, infrastructure addresses, access details, sender/recipient,
codes, tokens, cookie values, secret configurations and raw diagnostic logs are
intentionally absent from these public artifacts. The owner receives the actual
demo URL through the private task conversation.
