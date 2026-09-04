#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${SUDO_USER:-deraldinho}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

check_mode() {
  echo "node=$(hostname)"
  echo "os=$(source /etc/os-release; echo "$PRETTY_NAME")"
  echo "tailscale=$(tailscale ip -4 2>/dev/null || true)"
  echo "root=$(df -h / | awk 'NR==2 {print $2" total, "$4" free"}')"
  echo "docker=$(command -v docker || echo missing)"
  echo "compose=$(docker compose version 2>/dev/null || echo missing)"
  echo "timezone=$(timedatectl show -p Timezone --value)"
  echo "failed_units=$(systemctl --failed --no-legend | wc -l)"
}

if [[ "${1:-}" == "--check" ]]; then
  check_mode
  exit 0
fi

if [[ $EUID -ne 0 ]]; then
  echo "Execute com sudo: sudo $0" >&2
  exit 2
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2 uidmap

timedatectl set-timezone America/Sao_Paulo

install -d -m 0755 /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "live-restore": true,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
JSON
systemctl enable --now docker
usermod -aG docker "$TARGET_USER"

install -d -m 0755 /etc/systemd/system/systemd-networkd-wait-online.service.d
cat > /etc/systemd/system/systemd-networkd-wait-online.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/lib/systemd/systemd-networkd-wait-online --any --timeout=30
EOF
systemctl daemon-reload
systemctl reset-failed systemd-networkd-wait-online.service || true
systemctl start systemd-networkd-wait-online.service || true

systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
install -d -m 0755 /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/99-homelab.conf <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
EOF

install -d -m 0755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-homelab.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 120
ClientAliveCountMax 2
EOF
sshd -t
systemctl reload ssh

install -d -o "$TARGET_USER" -g "$TARGET_USER" -m 0755 \
  "$TARGET_HOME/homelab/stacks" \
  "$TARGET_HOME/homelab/backups" \
  "$TARGET_HOME/homelab/state"

echo "CORE_HOST_BOOTSTRAP_OK"
echo "Reabra a sessão SSH para aplicar o grupo docker; reinicie o Core depois para aplicar integralmente a política de lid/sleep."
