#!/usr/bin/env bash
set -Eeuo pipefail

export MSYS_NO_PATHCONV=1
cd "$(dirname "${BASH_SOURCE[0]}")"

assert_eq() {
  local name="$1"
  local expected="$2"
  local actual="$3"
  if [[ "${actual}" != "${expected}" ]]; then
    printf 'DEVEX_SIMULATION_ASSERT_FAIL check=%s expected=%q actual=%q\n' \
      "${name}" "${expected}" "${actual}" >&2
    return 1
  fi
  printf 'DEVEX_SIMULATION_ASSERT_PASS check=%s\n' "${name}"
}

assert_cmd() {
  local name="$1"
  shift
  if ! "$@"; then
    printf 'DEVEX_SIMULATION_ASSERT_FAIL check=%s command_failed\n' "${name}" >&2
    return 1
  fi
  printf 'DEVEX_SIMULATION_ASSERT_PASS check=%s\n' "${name}"
}

cleanup() {
  local rc=0
  docker compose down -v --remove-orphans >/dev/null 2>&1 || rc=1

  local containers
  local volumes
  local networks
  containers="$(docker ps -aq --filter 'name=devex-sim-')"
  volumes="$(docker volume ls -q --filter 'name=devex-homelab-sim')"
  networks="$(docker network ls -q --filter 'name=devex-homelab-sim-net')"

  if [[ -n "${containers}" || -n "${volumes}" || -n "${networks}" ]]; then
    printf 'cleanup left resources: containers=%q volumes=%q networks=%q\n' \
      "${containers}" "${volumes}" "${networks}" >&2
    rc=1
  fi

  return "${rc}"
}

trap cleanup EXIT

docker compose config --quiet
docker compose build
docker compose up -d --wait --wait-timeout 90

core_health="$(docker inspect --format '{{.State.Health.Status}}' devex-sim-core)"
pentium_health="$(docker inspect --format '{{.State.Health.Status}}' devex-sim-pentium)"
assert_eq core_health healthy "${core_health}"
assert_eq pentium_health healthy "${pentium_health}"

core_uid="$(docker compose exec -T sim-core id -u | tr -d '\r')"
core_role="$(docker compose exec -T sim-core cat /state/role | tr -d '\r')"
assert_eq core_uid 1000 "${core_uid}"
assert_eq core_role homelab.compute "${core_role}"
assert_cmd core_workspace_readable docker compose exec -T sim-core test -r /workspace/docs/GDD.md
assert_cmd core_state_writable docker compose exec -T sim-core test -w /state

core_workspace_rw="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.RW}}{{end}}{{end}}' devex-sim-core)"
assert_eq core_workspace_rw false "${core_workspace_rw}"

pentium_uid="$(docker compose exec -T sim-pentium id -u | tr -d '\r')"
pentium_role="$(docker compose exec -T sim-pentium cat /state/role | tr -d '\r')"
assert_eq pentium_uid 1000 "${pentium_uid}"
assert_eq pentium_role homelab.control "${pentium_role}"
assert_cmd pentium_workspace_readable docker compose exec -T sim-pentium test -r /workspace/docs/GDD.md
assert_cmd pentium_state_writable docker compose exec -T sim-pentium test -w /state

pentium_workspace_rw="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.RW}}{{end}}{{end}}' devex-sim-pentium)"
assert_eq pentium_workspace_rw false "${pentium_workspace_rw}"

if ! probe="$(docker compose exec -T sim-pentium sh -c 'printf probe | nc -w 2 sim-core 8080' | tr -d '\r')"; then
  printf 'DEVEX_SIMULATION_ASSERT_FAIL check=single_probe command_failed\n' >&2
  exit 1
fi
assert_eq single_probe DEVEX_SIM_CORE_OK "${probe}"

if ! timeout 10s docker compose exec -T sim-pentium sh -eu -c '
  pids=""
  probe_id=1
  while [ "$probe_id" -le 8 ]; do
    current_probe="$probe_id"
    (
      started="$(date +%s%3N)"
      result="$(printf probe | nc -w 5 sim-core 8080 | tr -d "\r")"
      rc=$?
      finished="$(date +%s%3N)"
      duration_ms=$((finished - started))
      if [ "$rc" -ne 0 ]; then
        printf "DEVEX_SIMULATION_CONCURRENCY_PROBE_FAIL probe=%s rc=%s duration_ms=%s reason=transport\n"           "$current_probe" "$rc" "$duration_ms" >&2
        exit 1
      fi
      if [ "$result" != "DEVEX_SIM_CORE_OK" ]; then
        printf "DEVEX_SIMULATION_CONCURRENCY_PROBE_FAIL probe=%s rc=0 duration_ms=%s reason=response actual=%s\n"           "$current_probe" "$duration_ms" "$result" >&2
        exit 1
      fi
      printf "DEVEX_SIMULATION_CONCURRENCY_PROBE_PASS probe=%s duration_ms=%s\n"         "$current_probe" "$duration_ms"
    ) &
    pids="$pids $!"
    probe_id=$((probe_id + 1))
  done
  failed=0
  for pid in $pids; do
    wait "$pid" || failed=1
  done
  exit "$failed"
'; then
  printf 'DEVEX_SIMULATION_ASSERT_FAIL check=concurrency_probe command_failed_or_deadline\n' >&2
  exit 1
fi
printf 'DEVEX_SIMULATION_ASSERT_PASS check=concurrency_probe\n'

printf 'DEVEX_SIMULATION_CONCURRENCY_PASS\n'
printf 'DEVEX_SIMULATION_RUNTIME_PASS\n'

cleanup
trap - EXIT

printf 'DEVEX_SIMULATION_CLEANUP_PASS\n'
printf 'DEVEX_HOMELAB_SIMULATION_PASS\n'
