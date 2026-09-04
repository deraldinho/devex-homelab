#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
TARGET_DIR="$HOME/pentium-agent/health"
USER_UNIT_DIR="$HOME/.config/systemd/user"

install -d -m 0755 "$TARGET_DIR" "$USER_UNIT_DIR"
install -m 0755 "$SCRIPT_DIR/heartbeat.py" "$TARGET_DIR/heartbeat.py"
install -m 0644 "$SCRIPT_DIR/config.json" "$TARGET_DIR/config.json"
install -m 0755 \
  "$REPO_ROOT/infrastructure/network/health.py" \
  "$TARGET_DIR/network_health.py"
install -m 0644 \
  "$REPO_ROOT/infrastructure/network/inventory.json" \
  "$TARGET_DIR/network_inventory.json"
install -m 0644 \
  "$SCRIPT_DIR/systemd/pentium-heartbeat.service" \
  "$USER_UNIT_DIR/pentium-heartbeat.service"
install -m 0644 \
  "$SCRIPT_DIR/systemd/pentium-heartbeat.timer" \
  "$USER_UNIT_DIR/pentium-heartbeat.timer"

systemctl --user daemon-reload
systemctl --user enable --now pentium-heartbeat.timer
systemctl --user start pentium-heartbeat.service

systemctl --user is-enabled pentium-heartbeat.timer
systemctl --user is-active pentium-heartbeat.timer
cat "$HOME/pentium-agent/data/health/latest.json"
