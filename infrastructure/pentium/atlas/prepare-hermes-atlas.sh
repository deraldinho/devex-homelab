#!/usr/bin/env bash
set -euo pipefail

command -v hermes >/dev/null 2>&1 || {
  echo "Hermes CLI nao encontrado no PATH" >&2
  exit 2
}

if ! hermes profile show atlas >/dev/null 2>&1; then
  hermes profile create atlas --no-alias --no-skills
fi

hermes -p atlas skills opt-out --remove --yes >/dev/null

TOOLSETS=(
  web search browser terminal file code_execution vision image_gen video tts
  skills memory session_search delegation cronjob clarify messaging todo kanban
  debugging safe spotify homeassistant discord discord_admin feishu_doc feishu_drive
  yuanbao rl
)

for toolset in "${TOOLSETS[@]}"; do
  hermes -p atlas tools disable "${toolset}" >/dev/null 2>&1 || true
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONPATH="$(dirname "$(dirname "$(dirname "${SCRIPT_DIR}")")")${PYTHONPATH:+:${PYTHONPATH}}" \
  python3 -m infrastructure.pentium.atlas.hermes_preflight
