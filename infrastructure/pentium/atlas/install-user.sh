#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="${HOME}/pentium-agent"
TARGET_DIR="${TARGET_ROOT}/atlas"

install -d -m 0755 "${TARGET_DIR}"

for file in \
  __init__.py \
  state_model.py \
  health_engine.py \
  reaction_engine.py \
  journal.py \
  stimulus_model.py \
  stimulus_bus.py \
  stimulus_journal.py \
  stimulus_sources.py \
  observation_runtime.py \
  cli.py; do
  install -m 0644 "${SOURCE_DIR}/${file}" "${TARGET_DIR}/${file}"
done

for config in config.json observation_config.json; do
  install -m 0644 "${SOURCE_DIR}/${config}" "${TARGET_DIR}/${config}"
done

python3 -m py_compile \
  "${TARGET_DIR}/state_model.py" \
  "${TARGET_DIR}/health_engine.py" \
  "${TARGET_DIR}/reaction_engine.py" \
  "${TARGET_DIR}/journal.py" \
  "${TARGET_DIR}/stimulus_model.py" \
  "${TARGET_DIR}/stimulus_bus.py" \
  "${TARGET_DIR}/stimulus_journal.py" \
  "${TARGET_DIR}/stimulus_sources.py" \
  "${TARGET_DIR}/observation_runtime.py" \
  "${TARGET_DIR}/cli.py"

python3 -m json.tool "${TARGET_DIR}/config.json" >/dev/null
python3 -m json.tool "${TARGET_DIR}/observation_config.json" >/dev/null

echo "ATLAS_STATE_REACTION_INSTALL_PASS"
echo "ATLAS_OBSERVATION_INSTALL_PASS"
echo "run=cd ${TARGET_ROOT} && python3 -m atlas.cli --input <snapshot.json>"
