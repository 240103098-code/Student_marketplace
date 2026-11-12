#!/bin/bash
# Fixed installed root-only Compose; never uses candidate source configuration.
set -euo pipefail
test "$(id -u)" = 0
cd /opt/student-marketplace-cd/template
args=(--project-name student-marketplace-oracle-demo --env-file /etc/student-marketplace-demo/runtime.env)
if [ -e /etc/student-marketplace-demo/smtp.env ]; then
  test ! -L /etc/student-marketplace-demo/smtp.env
  test "$(stat -c %u:%a /etc/student-marketplace-demo/smtp.env)" = 0:600
  args+=(--env-file /etc/student-marketplace-demo/smtp.env)
fi
exec docker compose "${args[@]}" -f compose.yaml -f ops/oracle/compose.https.yaml "$@"
