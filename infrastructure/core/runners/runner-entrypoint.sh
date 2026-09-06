#!/usr/bin/env bash
set -euo pipefail
if [[ ! -x /runner/run.sh ]]; then
  cp -a /opt/runner-dist/. /runner/
fi
cd /runner
if [[ ! -f .runner ]]; then
  : "${REPO_URL:?REPO_URL required}"
  : "${RUNNER_TOKEN:?RUNNER_TOKEN required for initial registration}"
  : "${RUNNER_NAME:?RUNNER_NAME required}"
  : "${RUNNER_LABELS:?RUNNER_LABELS required}"
  ./config.sh --unattended --replace \
    --url "$REPO_URL" \
    --token "$RUNNER_TOKEN" \
    --name "$RUNNER_NAME" \
    --work _work \
    --labels "$RUNNER_LABELS"
fi
unset RUNNER_TOKEN || true
exec ./run.sh
