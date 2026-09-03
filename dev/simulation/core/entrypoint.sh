#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "${DEVEX_NODE_ROLE}" > /state/role
printf '%s\n' "${DEVEX_NODE_NAME}" > /state/name

exec socat TCP-LISTEN:8080,reuseaddr,fork SYSTEM:'printf "DEVEX_SIM_CORE_OK\n"'
