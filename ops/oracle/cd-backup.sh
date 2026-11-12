#!/bin/bash
# Fixed installed private pre-activation backup. Caller already stopped app/proxy.
set -euo pipefail
test "$(id -u)" = 0
umask 077
root=/var/backups/student-marketplace-cd
install -d -o root -g root -m 700 "$root"
test "$(df --output=avail -k "$root" | tail -1)" -gt 4194304
test "$(find "$root" -mindepth 1 -maxdepth 1 -type d | wc -l)" -lt 20
destination="$root/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -m 700 "$destination"
compose=/opt/student-marketplace-cd/compose.sh
test -z "$("$compose" ps --status running -q app)"
test -z "$("$compose" ps --status running -q proxy)"
"$compose" exec -T db pg_dump -U marketplace -d marketplace --format=custom > "$destination/database.dump"
"$compose" exec -T db pg_restore --list < "$destination/database.dump" > /dev/null
volume=student-marketplace-oracle-demo_uploads
test "$(docker volume inspect "$volume" --format '{{index .Labels "com.docker.compose.project"}}')" = student-marketplace-oracle-demo
test "$(docker volume inspect "$volume" --format '{{index .Labels "com.docker.compose.volume"}}')" = uploads
image=$(python3 -c 'import json; print(json.load(open("/opt/student-marketplace-cd/state.json"))["image"])')
[[ "$image" =~ ^sha256:[a-f0-9]{64}$ ]]
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 10001:10001 --memory 256m --cpus 0.5 --pids-limit 32 \
  --mount type=volume,source="$volume",target=/data/uploads,readonly \
  "$image" python -c 'import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode="w|"); t.add("/data/uploads",arcname="uploads"); t.close()' > "$destination/uploads.tar"
cp -p /etc/student-marketplace-demo/runtime.env "$destination/runtime.env"
if [ -e /etc/student-marketplace-demo/smtp.env ]; then
  cp -p /etc/student-marketplace-demo/smtp.env "$destination/smtp.env"
fi
cp -p /opt/student-marketplace-cd/state.json "$destination/release.json"
sha256sum "$destination/database.dump" "$destination/uploads.tar" > "$destination/SHA256SUMS"
echo 'Owned private deployment backup completed.'
