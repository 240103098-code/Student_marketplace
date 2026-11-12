#!/bin/bash
# Installed root-owned executable: the dedicated SSH key always invokes this.
set -euo pipefail
test "$(id -un)" = marketplace-deploy
test "${#SSH_ORIGINAL_COMMAND}" -le 256
# Never eval or interpolate a request as executable shell code.
printf '%s' "$SSH_ORIGINAL_COMMAND" | /usr/bin/sudo -n /usr/bin/python3 -I /opt/student-marketplace-cd/controller.py
