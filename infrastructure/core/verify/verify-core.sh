#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "CORE_VERIFY_FAIL: $*" >&2
  exit 1
}

[[ "$(hostname)" == "core" ]] || fail "hostname"
source /etc/os-release
[[ "${VERSION_ID}" == "26.04" ]] || fail "ubuntu-version"

[[ -n "$(tailscale ip -4 2>/dev/null)" ]] || fail "tailscale"
[[ "$(timedatectl show -p Timezone --value)" == "America/Sao_Paulo" ]] || fail "timezone"
systemctl is-active --quiet docker || fail "docker-service"
docker version --format 'docker={{.Server.Version}}'
docker compose version

for target in sleep.target suspend.target hibernate.target hybrid-sleep.target; do
  [[ "$(systemctl is-enabled "$target" 2>/dev/null)" == "masked" ]] || fail "$target"
done

[[ -r /etc/docker/daemon.json ]] || fail "daemon-json"
grep -q '"live-restore": true' /etc/docker/daemon.json || fail "live-restore"
grep -q '"max-size": "10m"' /etc/docker/daemon.json || fail "docker-log-size"
grep -q '"max-file": "3"' /etc/docker/daemon.json || fail "docker-log-files"

grep -q 'HandleLidSwitch=ignore' /etc/systemd/logind.conf.d/99-homelab.conf || fail "lid-switch"
grep -q 'PasswordAuthentication no' /etc/ssh/sshd_config.d/99-homelab.conf || fail "ssh-password"
grep -q 'PermitRootLogin no' /etc/ssh/sshd_config.d/99-homelab.conf || fail "ssh-root"
grep -q 'PubkeyAuthentication yes' /etc/ssh/sshd_config.d/99-homelab.conf || fail "ssh-pubkey"
grep -q 'systemd-networkd-wait-online --any --timeout=30' \
  /etc/systemd/system/systemd-networkd-wait-online.service.d/override.conf || fail "wait-online"

for tool in javac ant node npm codex; do
  if command -v "$tool" >/dev/null 2>&1; then
    fail "host-toolchain:$tool"
  fi
done
[[ ! -d "$HOME/projects" ]] || fail "host-projects-dir"

smoke_dir="$HOME/homelab/stacks/smoke"
[[ -f "$smoke_dir/compose.yaml" ]] || fail "smoke-manifest"
smoke_output="$(cd "$smoke_dir" && docker compose run --rm smoke)"
grep -q 'CORE_CONTAINER_SMOKE_OK' <<<"$smoke_output" || fail "container-smoke"

failed_units="$(systemctl --failed --no-legend | wc -l)"
[[ "$failed_units" -eq 0 ]] || fail "failed-units:$failed_units"

echo "CORE_COMPUTE_CERTIFICATION_PASS"
