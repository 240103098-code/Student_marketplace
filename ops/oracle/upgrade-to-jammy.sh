#!/bin/bash
# Run only on the explicitly authorized fresh Focal Oracle ARM demo host.
set -euo pipefail
test "$(id -u)" = 0
. /etc/os-release
test "$ID" = ubuntu
test "$VERSION_ID" = 20.04
test "$(dpkg --print-architecture)" = arm64
test "$(df --output=avail -k / | tail -1)" -gt 15728640
/usr/sbin/sshd -t
phase=${1:?Use prepare or release}
test "$phase" = prepare -o "$phase" = release
install -d -m 700 /root/marketplace-os-upgrade
umask 077
if [ "$phase" = prepare ]; then
test ! -e /root/marketplace-os-upgrade/started
cp -a /etc/ssh /root/marketplace-os-upgrade/ssh
cp -a /etc/apt /root/marketplace-os-upgrade/apt
cp -a /etc/netplan /root/marketplace-os-upgrade/netplan
iptables-save > /root/marketplace-os-upgrade/iptables.v4
ip6tables-save > /root/marketplace-os-upgrade/iptables.v6
dpkg-query -W > /root/marketplace-os-upgrade/packages.before
touch /root/marketplace-os-upgrade/started
fi
exec >> /root/marketplace-os-upgrade/upgrade.log 2>&1
date -u
# Canonical Oracle guidance: prevent agent package-lock conflicts, reboot restores.
if snap list oracle-cloud-agent >/dev/null 2>&1; then snap stop oracle-cloud-agent; fi
if systemctl list-unit-files unified-monitoring-agent.service --no-legend | grep -q unified-monitoring; then
  systemctl stop unified-monitoring-agent.service
fi
export DEBIAN_FRONTEND=noninteractive
restart_agents() {
  if snap list oracle-cloud-agent >/dev/null 2>&1; then snap start oracle-cloud-agent || true; fi
  if systemctl list-unit-files unified-monitoring-agent.service --no-legend | grep -q unified-monitoring; then
    systemctl start unified-monitoring-agent.service || true
  fi
}
trap restart_agents EXIT
if [ "$phase" = prepare ]; then
  apt-get update
  apt-get -y -o Dpkg::Options::=--force-confold dist-upgrade
  /usr/sbin/sshd -t
  touch /root/marketplace-os-upgrade/prepared
  # Reboot, if requested, is an explicit separately monitored action.
  exit 0
fi
test -e /root/marketplace-os-upgrade/prepared
test ! -e /var/run/reboot-required
test "$(awk -F= '/^Prompt=/{print $2}' /etc/update-manager/release-upgrades)" = lts
# No development release, codename substitution, automatic reboot or paid support.
# Existing SSH/cloud network configuration is retained by dpkg --force-confold.
# Do not kill dpkg mid-transition: monitoring has a bounded budget, package
# operations run under a detached systemd service without a kill timeout.
do-release-upgrade -f DistUpgradeViewNonInteractive
. /etc/os-release
test "$VERSION_ID" = 22.04
/usr/sbin/sshd -t
touch /root/marketplace-os-upgrade/ready-for-reviewed-reboot
date -u
