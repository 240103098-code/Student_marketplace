#!/bin/bash
# Official signed Ubuntu ARM64 packages; no convenience installer or daemon prune.
set -euo pipefail
test "$(id -u)" = 0
. /etc/os-release
test "$ID" = ubuntu
test "$VERSION_ID" = 22.04
test "$VERSION_CODENAME" = jammy
test "$(dpkg --print-architecture)" = arm64
/usr/sbin/sshd -t
for package in docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc docker-buildx; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
    echo "Conflicting package: $package; manual review required" >&2; exit 1
  fi
done
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg
install -d -m 755 /etc/apt/keyrings
key=$(mktemp)
trap 'rm -f "$key"' EXIT
curl --fail --silent --show-error --location --max-time 60 https://download.docker.com/linux/ubuntu/gpg -o "$key"
fingerprint=$(gpg --batch --show-keys --with-colons "$key" | awk -F: '$1=="fpr"{print $10; exit}')
test "$fingerprint" = 9DC858229FC7DD38854AE2D88D81803C0EBFCD88
install -m 644 "$key" /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: jammy
Components: stable
Architectures: arm64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
install -d -m 700 /root/marketplace-runtime
umask 077
if [ ! -e /root/marketplace-runtime/docker-packages.txt ]; then
packages=()
for package in docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; do
  version=$(apt-cache policy "$package" | awk '/Candidate:/{print $2}')
  test -n "$version" && test "$version" != '(none)'
  packages+=("$package=$version")
done
printf '%s\n' "${packages[@]}" > /root/marketplace-runtime/docker-packages.txt
echo 'Exact candidate versions recorded; review before rerunning to install.'
exit 0
fi
packages=()
while IFS= read -r spec; do
  [[ "$spec" =~ ^(docker-ce|docker-ce-cli|containerd\.io|docker-buildx-plugin|docker-compose-plugin)=[0-9][A-Za-z0-9.:+~_-]+$ ]]
  packages+=("$spec")
done < /root/marketplace-runtime/docker-packages.txt
test "${#packages[@]}" = 5
test "$(printf '%s\n' "${packages[@]}" | cut -d= -f1 | sort -u | wc -l)" = 5
apt-get install -y "${packages[@]}"
systemctl enable --now docker
docker version --format '{{.Server.Version}} {{.Server.Arch}}'
docker compose version
docker buildx version
