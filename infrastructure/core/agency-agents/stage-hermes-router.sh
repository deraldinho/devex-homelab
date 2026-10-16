#!/usr/bin/env bash
# Generate Agency Agents Hermes router in an ISOLATED staging directory.
# NEVER run this script on the pentium. Does not modify the live Hermes profile.
set -euo pipefail

REPO_URL="https://github.com/msitarzewski/agency-agents.git"
PINNED_SHA="f99f6aa910a442b0197b768ce0ea7751e35e2060"
STAGE="${1:-}"
if [[ -z "$STAGE" || "$STAGE" != /* || "$STAGE" == / || "$STAGE" == "$HOME" || -e "$STAGE" ]]; then
  echo "Usage: stage-hermes-router.sh /absolute/NEW/staging/directory" >&2
  exit 2
fi
if [[ "$(hostname -s)" != "core" && "${ATLAS_CORE_STAGING_CONTAINER:-}" != "1" ]]; then
  echo "DENY: staging only on core or a dedicated disposable core container" >&2
  exit 3
fi
command -v git >/dev/null
command -v python3 >/dev/null
command -v bash >/dev/null

mkdir -p "$STAGE"
trap 'echo "Staging kept at: $STAGE (no live installation)"' EXIT
git clone --no-checkout "$REPO_URL" "$STAGE/source"
git -C "$STAGE/source" checkout --detach "$PINNED_SHA"
actual="$(git -C "$STAGE/source" rev-parse HEAD)"
[[ "$actual" == "$PINNED_SHA" ]] || { echo "Repository SHA mismatch" >&2; exit 4; }
[[ -f "$STAGE/source/LICENSE" ]] || { echo "Missing LICENSE" >&2; exit 4; }

# Review pinned upstream code, policies and dependency scripts BEFORE using
# any plugin in a non-disposable Hermes profile.
bash "$STAGE/source/scripts/convert.sh" --tool hermes
plugin="$STAGE/source/integrations/hermes/agency-agents-router"
# Static, fail-closed validation of the pinned generator output.
# Never import/execute generated plugin code or change live Hermes configuration.
python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/plugin_validator.py" "$STAGE"

# Stage only. This intentionally does NOT call scripts/install.sh against a
# real ~/.hermes, modify ~/.hermes/config.yaml, start LLMs or restart systemd.
echo "STAGE_READY source=$PINNED_SHA path=$plugin"
echo "Next gate: independent code review, backup/restore, profile tool audit, physical certification."
