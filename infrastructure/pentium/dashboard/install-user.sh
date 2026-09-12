#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/pentium-agent/dashboard"
USER_UNIT_DIR="$HOME/.config/systemd/user"
RUNTIME_DIR="$HOME/pentium-agent/atlas/runtime"

install -d -m 0755 "$TARGET_DIR" "$USER_UNIT_DIR"
if [[ -d "${RUNTIME_DIR}" ]]; then
  find "${RUNTIME_DIR}" -type f -exec chmod 0600 {} +
fi
install -m 0755 "$SCRIPT_DIR/atlas_dashboard.py" "$TARGET_DIR/atlas_dashboard.py"
install -m 0644 "$SCRIPT_DIR/dashboard_collectors.py" "$TARGET_DIR/dashboard_collectors.py"
install -m 0644 "$SCRIPT_DIR/dashboard_chat.py" "$TARGET_DIR/dashboard_chat.py"
install -m 0644 "$SCRIPT_DIR/dashboard_event_store.py" "$TARGET_DIR/dashboard_event_store.py"
install -m 0644 "$SCRIPT_DIR/dashboard.html" "$TARGET_DIR/dashboard.html"
install -m 0644 "$SCRIPT_DIR/atlas-avatar-motion.js" "$TARGET_DIR/atlas-avatar-motion.js"
install -m 0644 "$SCRIPT_DIR/atlas-avatar-engine.js" "$TARGET_DIR/atlas-avatar-engine.js"
install -m 0644 "$SCRIPT_DIR/atlas-avatar-renderer.js" "$TARGET_DIR/atlas-avatar-renderer.js"
install -m 0644 "$SCRIPT_DIR/atlas-pet-standing.png" "$TARGET_DIR/atlas-pet-standing.png"
install -m 0644 "$SCRIPT_DIR/atlas-pet-sitting.png" "$TARGET_DIR/atlas-pet-sitting.png"
install -m 0644 "$SCRIPT_DIR/atlas-pet-poke.png" "$TARGET_DIR/atlas-pet-poke.png"
install -m 0755 "$SCRIPT_DIR/fetch-pixi.sh" "$TARGET_DIR/fetch-pixi.sh"
"$TARGET_DIR/fetch-pixi.sh" "$TARGET_DIR/pixi.min.js"
install -m 0644 "$SCRIPT_DIR/config.json" "$TARGET_DIR/config.json"
install -m 0644 "$SCRIPT_DIR/cognitive_panel_certification.py" "$TARGET_DIR/cognitive_panel_certification.py"
install -m 0644 "$SCRIPT_DIR/systemd/atlas-dashboard.service" "$USER_UNIT_DIR/atlas-dashboard.service"

python3 -m py_compile "$TARGET_DIR/atlas_dashboard.py" "$TARGET_DIR/dashboard_collectors.py" "$TARGET_DIR/dashboard_chat.py" "$TARGET_DIR/dashboard_event_store.py" "$TARGET_DIR/cognitive_panel_certification.py"
systemctl --user daemon-reload
systemctl --user enable atlas-dashboard.service
systemctl --user restart atlas-dashboard.service
systemctl --user is-enabled atlas-dashboard.service
systemctl --user is-active atlas-dashboard.service
