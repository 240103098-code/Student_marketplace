#!/bin/bash
# Root-only convenience wrapper. Never prints expanded configuration.
set -euo pipefail
test "$(id -u)" = 0
private_file() {
  test -f "$1" && test ! -L "$1"
  test "$(stat -c %u "$1")" = 0
  test "$(stat -c %a "$1")" = 600
}
private_file /etc/student-marketplace-demo/runtime.env
cd /opt/student-marketplace-demo/current
args=(--project-name student-marketplace-oracle-demo --env-file /etc/student-marketplace-demo/runtime.env)
if [ -e /etc/student-marketplace-demo/smtp.env ]; then
  private_file /etc/student-marketplace-demo/smtp.env
  args+=(--env-file /etc/student-marketplace-demo/smtp.env)
fi
exec docker compose "${args[@]}" -f compose.yaml -f ops/oracle/compose.https.yaml "$@"
