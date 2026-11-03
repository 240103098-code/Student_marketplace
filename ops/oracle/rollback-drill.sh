#!/bin/bash
# First historical deployment occurs NOW for this drill, not past production.
# App input trees are identical: this tests digest/config selection and retention,
# not different application binaries or schema downgrade compatibility. No mail.
set -euo pipefail
test "$(id -u)" = 0
umask 077
exec 9>/root/marketplace-runtime/rollback-drill.lock
flock -w 300 9
directory=/root/marketplace-runtime/rollback-drill
runtime=/etc/student-marketplace-demo/runtime.env
compose=/opt/student-marketplace-demo/current/ops/oracle/demo-compose.sh
current=student-marketplace-demo@sha256:d13ce798cd83f4dd37b3631d17e85f5a7de8f431d930f1a5e9b4c13133f05cd2
phase=${1:?prepare HISTORICAL_DIGEST_IMAGE or baseline/upgrade/rollback/final/recover}
private_file() {
  test -f "$1" && test ! -L "$1"
  test "$(stat -c %u "$1")" = 0 && test "$(stat -c %a "$1")" = 600
}
private_file "$runtime"
atomic_select() {
  private_file "$1"
  temporary="${runtime}.drill.$$"
  install -o root -g root -m 600 "$1" "$temporary"
  mv -fT -- "$temporary" "$runtime"
}
start_app() {
  "$compose" config --quiet
  "$compose" up --detach --no-build --no-deps --force-recreate --wait --wait-timeout 120 app >/dev/null 2>&1
}
recover() {
  trap - EXIT
  atomic_select "$directory/current.env"
  start_app
  printf '%s\n' recovered-current > "$directory/state"
  systemctl stop marketplace-drill-recovery.timer 2>/dev/null || true
  echo 'Verified current-main config/image recovered; persistent volumes preserved.'
}
if [ "$phase" = recover ]; then recover; exit 0; fi
if [ "$phase" = prepare ]; then
  historical=${2:?Reviewed native historical digest image required}
  [[ "$historical" =~ ^student-marketplace-history@sha256:[a-f0-9]{64}$ ]]
  test ! -e "$directory"
  test "$(docker image inspect "$historical" --format '{{.Architecture}}')" = arm64
  test "$(docker image inspect "$historical" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = 99561068b8f38f4d04bb1be7fb44d7320dd20ff7
  test "$(docker image inspect "$current" --format '{{.Architecture}}')" = arm64
  test "$(docker image inspect "$current" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')" = c3869077ef70d1c2bfdc14f6aa87daa25108bbbb
  test "$("$compose" exec -T db psql -U marketplace -d marketplace -Atc 'SELECT version_num FROM alembic_version;')" = 0003_listings
  test "$("$compose" exec -T db psql -U marketplace -d marketplace -Atc 'SELECT count(*) FROM users WHERE avatar_path IS NOT NULL;')" = 1
  install -d -m 700 "$directory"
  cp -p "$runtime" "$directory/current.env"
  python3 - "$directory/current.env" "$directory/historical.env" "$current" "$historical" <<'PY'
import pathlib,sys
source,target,current,historical=sys.argv[1:]
value=pathlib.Path(source).read_text()
old='MARKETPLACE_IMAGE='+current
assert value.count(old)==1
pathlib.Path(target).write_text(value.replace(old,'MARKETPLACE_IMAGE='+historical))
PY
  chmod 600 "$directory/historical.env"
  printf '%s\n' prepared > "$directory/state"
  echo 'Private stable-config snapshots prepared; only image references differ.'
  exit 0
fi
private_file "$directory/current.env"
private_file "$directory/historical.env"
trap 'status=$?; if [ "$status" -ne 0 ]; then recover; fi' EXIT
state=$(cat "$directory/state")
case "$phase" in
  baseline)
    test "$state" = prepared
    # Independent fallback survives loss of the operator process/SSH connection.
    systemd-run --unit marketplace-drill-recovery --on-active=20m /bin/bash "$(readlink -f "$0")" recover >/dev/null
    atomic_select "$directory/historical.env"
    next=historical-baseline
    ;;
  upgrade)
    test "$state" = historical-baseline
    atomic_select "$directory/current.env"
    next=upgraded-current
    ;;
  rollback)
    test "$state" = upgraded-current
    atomic_select "$directory/historical.env"
    next=rolled-back-historical
    ;;
  final)
    test "$state" = rolled-back-historical
    atomic_select "$directory/current.env"
    next=final-current
    ;;
  *) echo 'Unknown drill phase' >&2; exit 1 ;;
esac
start_app
printf '%s\n' "$next" > "$directory/state"
if [ "$phase" = final ]; then
  systemctl stop marketplace-drill-recovery.timer
fi
echo "Drill stage $next healthy; external verification still required."
