#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/pentium-agent/agent"

install -d -m 0755 "${TARGET_DIR}" "${TARGET_DIR}/actions"

install -m 0644 "${SOURCE_DIR}/agent.py" "${TARGET_DIR}/agent.py"
install -m 0644 "${SOURCE_DIR}/cli.py" "${TARGET_DIR}/cli.py"
install -m 0644 "${SOURCE_DIR}/ssh_transport.py" "${TARGET_DIR}/ssh_transport.py"
install -m 0644 "${SOURCE_DIR}/managed_inventory.py" "${TARGET_DIR}/managed_inventory.py"
install -m 0644 "${SOURCE_DIR}/managed_read.py" "${TARGET_DIR}/managed_read.py"
install -m 0644 "${SOURCE_DIR}/config.json" "${TARGET_DIR}/config.json"
install -m 0644 "${SOURCE_DIR}/actions/x99_status.py" "${TARGET_DIR}/actions/x99_status.py"

python3 -m py_compile \
  "${TARGET_DIR}/agent.py" \
  "${TARGET_DIR}/cli.py" \
  "${TARGET_DIR}/ssh_transport.py" \
  "${TARGET_DIR}/managed_inventory.py" \
  "${TARGET_DIR}/managed_read.py" \
  "${TARGET_DIR}/actions/x99_status.py"

python3 -m json.tool "${TARGET_DIR}/config.json" >/dev/null

echo "PENTIUM_AGENT_INSTALL_PASS"
echo "PENTIUM_AGENT_MANAGED_SSH_READ_M1_INSTALL_PASS"
echo "run=python3 ${TARGET_DIR}/cli.py x99.status"
