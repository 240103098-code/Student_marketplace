#!/bin/bash
# Run in a maintenance window: caller stops app/proxy to keep DB+uploads aligned.
set -euo pipefail
test "$(id -u)" = 0
umask 077
root=/var/backups/student-marketplace-demo
install -d -m 700 "$root"
test "$(df --output=avail -k "$root" | tail -1)" -gt 4194304
test "$(find "$root" -mindepth 1 -maxdepth 1 -type d | wc -l)" -lt 20
destination="$root/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -m 700 "$destination"
compose=/opt/student-marketplace-demo/current/ops/oracle/demo-compose.sh
test -z "$("$compose" ps --status running -q app)"
test -z "$("$compose" ps --status running -q proxy)"
"$compose" exec -T db pg_dump -U marketplace -d marketplace --format=custom > "$destination/database.dump"
"$compose" exec -T db psql -v ON_ERROR_STOP=1 -U marketplace -d marketplace -Atc \
  'SELECT version_num FROM alembic_version; SELECT count(*) FROM users; SELECT count(*) FROM listings; SELECT count(*) FROM listing_photos;' > "$destination/database-state.txt"
test "$(head -1 "$destination/database-state.txt")" = 0003_listings
image=$("$compose" images -q app)
test -n "$image"
volume=student-marketplace-oracle-demo_uploads
test "$(docker volume inspect "$volume" --format '{{index .Labels "com.docker.compose.project"}}')" = student-marketplace-oracle-demo
test "$(docker volume inspect "$volume" --format '{{index .Labels "com.docker.compose.volume"}}')" = uploads
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 10001:10001 --memory 256m --cpus 0.5 --pids-limit 32 \
  --mount type=volume,source="$volume",target=/data/uploads,readonly \
  "$image" python -c 'import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode="w|"); t.add("/data/uploads",arcname="uploads"); t.close()' > "$destination/uploads.tar"
cp -p /etc/student-marketplace-demo/runtime.env "$destination/runtime.env"
if [ -e /etc/student-marketplace-demo/smtp.env ]; then
  cp -p /etc/student-marketplace-demo/smtp.env "$destination/smtp.env"
fi
cp /opt/student-marketplace-demo/current/RELEASE-SHA "$destination/RELEASE-SHA"
docker image inspect "$image" --format '{{.Id}}' > "$destination/APP-IMAGE"
sha256sum "$destination/database.dump" "$destination/uploads.tar" "$destination/database-state.txt" > "$destination/SHA256SUMS"
echo 'Owned root-private backup completed. Retain independently; no automatic deletion.'
