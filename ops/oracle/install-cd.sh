#!/bin/bash
# One-time installation ONLY after explicit owner consent and independent review.
# Usage: install-cd.sh REVIEWED_BUNDLE_DIRECTORY NEW_CI_PUBLIC_KEY_FILE CONFIG_JSON
# CONFIG_JSON contains only hostname and the independently verified workflow_id.
set -euo pipefail
test "$(id -u)" = 0
test "$#" = 3
umask 077
bundle=$(realpath -e -- "$1")
public=$(realpath -e -- "$2")
config=$(realpath -e -- "$3")
target=/opt/student-marketplace-cd
test ! -e "$target"
test ! -e /etc/sudoers.d/marketplace-deploy
test ! -e /etc/ssh/sshd_config.d/90-marketplace-deploy.conf
test ! -e /var/lib/marketplace-deploy && test ! -L /var/lib/marketplace-deploy
if id marketplace-deploy >/dev/null 2>&1; then echo 'Dedicated account already exists; review manually.' >&2; exit 1; fi
test "$(uname -m)" = aarch64
test "$(. /etc/os-release; echo "$VERSION_ID")" = 22.04
for original in "$bundle" "$public" "$config"; do
  checked="$original"
  while :; do
    test ! -L "$checked" && test "$(stat -c %u "$checked")" = 0
    test -z "$(find "$checked" -maxdepth 0 -perm /022 -print)"
    test "$checked" != / || break
    checked=$(dirname -- "$checked")
  done
done
for file in tools/oracle_cd.py ops/oracle/cd-gateway.sh ops/oracle/cd-compose.sh ops/oracle/cd-backup.sh compose.yaml ops/oracle/compose.https.yaml ops/oracle/Caddyfile; do
  test -f "$bundle/$file" && test ! -L "$bundle/$file"
  test "$(stat -c %u "$bundle/$file")" = 0
  test -z "$(find "$bundle/$file" -perm /022 -print)"
done
ci_public_key=$(python3 - "$public" <<'PY'
import pathlib,re,sys
key=pathlib.Path(sys.argv[1]).read_text().strip()
assert re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}(?: [A-Za-z0-9._-]{1,64})?',key)
print(key)
PY
)
python3 - "$config" <<'PY'
import json,pathlib,re,sys
configuration=json.loads(pathlib.Path(sys.argv[1]).read_text())
assert set(configuration)=={'hostname','workflow_id'}
assert re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,251}[a-z0-9]',configuration['hostname'])
assert type(configuration['workflow_id']) is int and configuration['workflow_id']>0
PY
install -d -o root -g root -m 711 "$target"
install -d -o root -g root -m 700 "$target/releases" "$target/template" "$target/template/ops" "$target/template/ops/oracle"
install -o root -g root -m 600 "$bundle/tools/oracle_cd.py" "$target/controller.py"
install -o root -g root -m 755 "$bundle/ops/oracle/cd-gateway.sh" "$target/gateway.sh"
install -o root -g root -m 700 "$bundle/ops/oracle/cd-compose.sh" "$target/compose.sh"
install -o root -g root -m 700 "$bundle/ops/oracle/cd-backup.sh" "$target/backup.sh"
install -o root -g root -m 600 "$bundle/compose.yaml" "$target/template/compose.yaml"
install -o root -g root -m 600 "$bundle/ops/oracle/compose.https.yaml" "$target/template/ops/oracle/compose.https.yaml"
install -o root -g root -m 644 "$bundle/ops/oracle/Caddyfile" "$target/template/ops/oracle/Caddyfile"
install -o root -g root -m 600 "$config" "$target/config.json"
git -c core.hooksPath=/dev/null init --bare "$target/source.git" >/dev/null
git -c core.hooksPath=/dev/null --git-dir="$target/source.git" fetch --no-tags --no-recurse-submodules \
  https://github.com/240103098-code/Student_marketplace.git +refs/heads/main:refs/heads/main >/dev/null 2>&1
python3 -I - "$target" <<'PY'
import importlib.util,json,pathlib,re,sys
root=pathlib.Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('reviewed_cd',root/'controller.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
host=module.Host({'image':'sha256:'+'0'*64})
identifier=host.compose('ps','-q','app').stdout.decode().strip()
assert re.fullmatch('[a-f0-9]{12,64}',identifier)
container=json.loads(module.execute(['docker','inspect',identifier]).stdout)[0]
image=json.loads(module.execute(['docker','image','inspect',container['Image']]).stdout)[0]
sha=image['Config']['Labels']['org.opencontainers.image.revision']
assert re.fullmatch('[a-f0-9]{40}',sha) and image['Architecture']=='arm64' and image['Config']['User']=='10001:10001'
git=['git','-c','core.hooksPath=/dev/null','--git-dir',str(root/'source.git')]
module.execute(git+['merge-base','--is-ancestor',sha,'refs/heads/main'])
release=root/'releases'/sha;release.mkdir(mode=0o700)
module.extract_source(module.execute(git+['archive','--format=tar',sha]).stdout,release)
state={'sha':sha,'image':image['Id']}
module.atomic_json(root/'state.json',state)
module.Host(state).verify()
print('Existing healthy source/image baseline recorded; no application restart.')
PY
useradd --system --home-dir /var/lib/marketplace-deploy --shell /bin/sh marketplace-deploy
account_created=yes
disable_on_error() {
  if [ "${account_created:-}" = yes ]; then
    passwd -l marketplace-deploy >/dev/null 2>&1 || true
    rm -f -- /var/lib/marketplace-deploy/.ssh/authorized_keys /etc/sudoers.d/marketplace-deploy /etc/ssh/sshd_config.d/90-marketplace-deploy.conf
    sshd -t && systemctl reload ssh || true
  fi
}
trap disable_on_error ERR
install -d -o root -g root -m 755 /var/lib/marketplace-deploy /var/lib/marketplace-deploy/.ssh
printf 'restrict,command="/opt/student-marketplace-cd/gateway.sh" %s\n' "$ci_public_key" > /var/lib/marketplace-deploy/.ssh/authorized_keys
chown root:root /var/lib/marketplace-deploy/.ssh/authorized_keys
chmod 644 /var/lib/marketplace-deploy/.ssh/authorized_keys
printf '%s\n' 'marketplace-deploy ALL=(root) NOPASSWD:NOSETENV: /usr/bin/python3 -I /opt/student-marketplace-cd/controller.py' > /etc/sudoers.d/marketplace-deploy
chmod 440 /etc/sudoers.d/marketplace-deploy
visudo -cf /etc/sudoers.d/marketplace-deploy >/dev/null
cat > /etc/ssh/sshd_config.d/90-marketplace-deploy.conf <<'SSHD'
Match User marketplace-deploy
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    DisableForwarding yes
    PermitTTY no
    ForceCommand /opt/student-marketplace-cd/gateway.sh
Match all
SSHD
chmod 600 /etc/ssh/sshd_config.d/90-marketplace-deploy.conf
sshd -t
systemctl reload ssh
trap - ERR
echo 'Restricted deployment access installed; inspect effective sshd/sudo/key permissions before activation.'
