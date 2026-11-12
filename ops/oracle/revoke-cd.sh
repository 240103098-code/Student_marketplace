#!/bin/bash
# Revoke only this explicitly named deployment identity. Retain app/data/evidence.
set -euo pipefail
test "$(id -u)" = 0
test "$#" = 0
if id marketplace-deploy >/dev/null 2>&1; then passwd -l marketplace-deploy >/dev/null; fi
for file in /var/lib/marketplace-deploy/.ssh/authorized_keys /etc/sudoers.d/marketplace-deploy /etc/ssh/sshd_config.d/90-marketplace-deploy.conf; do
  if [ -e "$file" ]; then
    test -f "$file" && test ! -L "$file" && test "$(stat -c %u "$file")" = 0
    rm -- "$file"
  fi
done
sshd -t
systemctl reload ssh
echo 'Dedicated SSH/sudo access revoked; remove the oracle-demo environment secrets separately. App/data retained.'
