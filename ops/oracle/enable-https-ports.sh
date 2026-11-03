#!/bin/bash
# Run before Docker starts, so only host rules are persisted (not Docker chains).
set -euo pipefail
test "$(id -u)" = 0
command -v netfilter-persistent >/dev/null
if systemctl is-active --quiet docker; then
  echo 'Refusing to persist dynamic Docker firewall chains; review host rules separately.' >&2
  exit 1
fi
install -d -m 700 /root/marketplace-runtime
umask 077
if [ ! -e /root/marketplace-runtime/iptables.before-https.v4 ]; then
  iptables-save > /root/marketplace-runtime/iptables.before-https.v4
  ip6tables-save > /root/marketplace-runtime/iptables.before-https.v6
fi
for firewall in iptables ip6tables; do
  "$firewall" -C INPUT -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT 2>/dev/null ||
    "$firewall" -I INPUT 1 -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT
done
netfilter-persistent save
/usr/sbin/sshd -t
echo 'Only TCP 80/443 new-connection host rules added; prior rules and SSH preserved.'
