#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
core="$root/infrastructure/core"
compose=(docker compose -f "$core/stacks/smoke/compose.yaml")

cleanup() {
  "${compose[@]}" down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

bash -n "$core/bootstrap/core-host-bootstrap.sh"
bash -n "$core/verify/verify-core.sh"

"${compose[@]}" config --quiet
smoke="$("${compose[@]}" run --rm smoke)"
grep -q 'CORE_CONTAINER_SMOKE_OK' <<<"$smoke"

if grep -Eiq 'openjdk|javac|ant|nodejs|npm|codex' "$core/bootstrap/core-host-bootstrap.sh"; then
  echo 'CORE_POLICY_FAIL: project toolchain in host bootstrap' >&2
  exit 1
fi

if grep -Eq '/home/[^/]+/projects|~/projects' "$core/bootstrap/core-host-bootstrap.sh"; then
  echo 'CORE_POLICY_FAIL: host project workspace in bootstrap' >&2
  exit 1
fi

cleanup
trap - EXIT
printf 'CORE_REPO_POLICY_PASS\n'
