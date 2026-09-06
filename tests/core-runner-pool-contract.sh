#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base="$root/infrastructure/core/runners"
compose="$base/compose.yaml"
entry="$base/runner-entrypoint.sh"
dockerfile="$base/Dockerfile"

test -f "$compose"
test -f "$entry"
test -f "$dockerfile"

grep -q 'core-l2jtoren-01:' "$compose"
grep -q 'core-l2jtoren-02:' "$compose"
grep -q 'core-homelab-01:' "$compose"
grep -q 'core-l2jtoren-01-work' "$compose"
grep -q 'core-l2jtoren-02-work' "$compose"
grep -q 'core-homelab-01-work' "$compose"

grep -q 'l2jtoren,docker' "$compose"
grep -q 'devex-homelab,docker' "$compose"
! grep -Eq 'gh[pousr]_[A-Za-z0-9_]+' "$base"/*
echo CORE_RUNNER_POOL_CONTRACT_PASS
