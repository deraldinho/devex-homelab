#!/usr/bin/env bash
set -Eeuo pipefail

export MSYS_NO_PATHCONV=1
cd "$(dirname "${BASH_SOURCE[0]}")"

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
[[ "${core_health}" == "healthy" ]]
[[ "${pentium_health}" == "healthy" ]]

core_uid="$(docker compose exec -T sim-core id -u | tr -d '\r')"
core_role="$(docker compose exec -T sim-core cat /state/role | tr -d '\r')"
[[ "${core_uid}" == "1000" ]]
[[ "${core_role}" == "homelab.compute" ]]
docker compose exec -T sim-core test -r /workspace/docs/GDD.md
docker compose exec -T sim-core test -w /state

core_workspace_rw="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.RW}}{{end}}{{end}}' devex-sim-core)"
[[ "${core_workspace_rw}" == "false" ]]

pentium_uid="$(docker compose exec -T sim-pentium id -u | tr -d '\r')"
pentium_role="$(docker compose exec -T sim-pentium cat /state/role | tr -d '\r')"
[[ "${pentium_uid}" == "1000" ]]
[[ "${pentium_role}" == "homelab.control" ]]
docker compose exec -T sim-pentium test -r /workspace/docs/GDD.md
docker compose exec -T sim-pentium test -w /state

pentium_workspace_rw="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.RW}}{{end}}{{end}}' devex-sim-pentium)"
[[ "${pentium_workspace_rw}" == "false" ]]
probe="$(docker compose exec -T sim-pentium sh -c 'printf probe | nc -w 2 sim-core 8080' | tr -d '\r')"
[[ "${probe}" == "DEVEX_SIM_CORE_OK" ]]

docker compose exec -T sim-pentium sh -eu -c '
  pids=""
  for _ in 1 2 3 4 5 6 7 8; do
    (
      result="$(printf probe | nc -w 2 sim-core 8080 | tr -d "\r")"
      [ "$result" = "DEVEX_SIM_CORE_OK" ]
    ) &
    pids="$pids $!"
  done
  for pid in $pids; do
    wait "$pid"
  done
'

printf 'DEVEX_SIMULATION_CONCURRENCY_PASS\n'
printf 'DEVEX_SIMULATION_RUNTIME_PASS\n'

cleanup
trap - EXIT

printf 'DEVEX_SIMULATION_CLEANUP_PASS\n'
printf 'DEVEX_HOMELAB_SIMULATION_PASS\n'
