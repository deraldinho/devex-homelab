#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "${DEVEX_NODE_ROLE}" > /state/role
printf '%s\n' "${DEVEX_NODE_NAME}" > /state/name

while true; do
  printf 'DEVEX_SIM_CORE_OK\n' | nc -l -p 8080 -q 1 || true
done
