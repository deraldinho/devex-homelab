#!/usr/bin/env bash
set -euo pipefail

ATLAS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="${HOME}/pentium-agent"
VENV_DIR="${TARGET_ROOT}/.venv-discord"

command -v python3 >/dev/null 2>&1 || { echo "python3 nao encontrado" >&2; exit 2; }
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check -r "${ATLAS_DIR}/requirements-discord.txt"
"${VENV_DIR}/bin/python" -c 'import discord; print(discord.__version__)'
echo "ATLAS_DISCORD_RUNTIME_PREPARED"
