#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/pentium-agent/dashboard"
USER_UNIT_DIR="$HOME/.config/systemd/user"

install -d -m 0755 "$TARGET_DIR" "$USER_UNIT_DIR"
install -m 0755 "$SCRIPT_DIR/atlas_dashboard.py" "$TARGET_DIR/atlas_dashboard.py"
install -m 0644 "$SCRIPT_DIR/dashboard_collectors.py" "$TARGET_DIR/dashboard_collectors.py"
install -m 0644 "$SCRIPT_DIR/dashboard.html" "$TARGET_DIR/dashboard.html"
install -m 0644 "$SCRIPT_DIR/config.json" "$TARGET_DIR/config.json"
install -m 0644 "$SCRIPT_DIR/cognitive_panel_certification.py" "$TARGET_DIR/cognitive_panel_certification.py"
install -m 0644 "$SCRIPT_DIR/systemd/atlas-dashboard.service" "$USER_UNIT_DIR/atlas-dashboard.service"

python3 -m py_compile "$TARGET_DIR/atlas_dashboard.py" "$TARGET_DIR/dashboard_collectors.py" "$TARGET_DIR/cognitive_panel_certification.py"
systemctl --user daemon-reload
systemctl --user enable atlas-dashboard.service
systemctl --user restart atlas-dashboard.service
systemctl --user is-enabled atlas-dashboard.service
systemctl --user is-active atlas-dashboard.service
