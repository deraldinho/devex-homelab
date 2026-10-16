# CP-AA6: Safe disposable core staging, never activates Hermes or Atlas.
# This script runs the already-reviewed pinned repo staging tool and validator
# inside a no-mount, unprivileged disposable container on authenticated core.
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$stagePath = Join-Path $project "infrastructure\core\agency-agents\stage-hermes-router.sh"
$validatorPath = Join-Path $project "infrastructure\core\agency-agents\plugin_validator.py"
$ssh = "C:\Program Files\Git\usr\bin\ssh.exe"
if (!(Test-Path -LiteralPath $ssh -PathType Leaf)) { throw "Git OpenSSH is required" }
if (!(Test-Path -LiteralPath $stagePath -PathType Leaf)) { throw "Missing pinned stage script" }
if (!(Test-Path -LiteralPath $validatorPath -PathType Leaf)) { throw "Missing static validator" }
$stage64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($stagePath))
$validator64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($validatorPath))

$remote = @'
set -eu
echo CORE_STAGE_HOST="$(hostname)"
IMAGE_ID="$(docker image inspect --format '{{.Id}}' devex/core-homelab-runner:2.337.0)"
echo CORE_RUNNER_IMAGE_ID="$IMAGE_ID"
test "$IMAGE_ID" = "sha256:189cc2fb326f164e487d51cc0d36b0764504482b2673a21373f35145dd72955c" || { echo "DENY: unreviewed core staging image revision" >&2; exit 9; }
docker run --rm -i --pull=never --network bridge --read-only --tmpfs /tmp:rw,exec,nosuid,size=500m --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=96 --memory=768m --cpus=1 --user 65534:65534 -e HOME=/tmp/atlas-home -e ATLAS_CORE_STAGING_CONTAINER=1 --entrypoint /bin/bash devex/core-homelab-runner:2.337.0 -s <<'INNER_ATLAS_STAGE'
set -euo pipefail
mkdir -p /tmp/atlas-home /tmp/atlas-tools
printf '%s' '__STAGE_B64__' | base64 -d > /tmp/atlas-tools/stage-hermes-router.sh
printf '%s' '__VALIDATOR_B64__' | base64 -d > /tmp/atlas-tools/plugin_validator.py
bash /tmp/atlas-tools/stage-hermes-router.sh /tmp/atlas-agency-stage-20261013
python3 - <<'PY'
import json
import importlib.util
from pathlib import Path
root = Path('/tmp/atlas-agency-stage-20261013/source/integrations/hermes/agency-agents-router')
data = json.loads((root / 'data/agents.json').read_text(encoding='utf-8'))
slugs = {agent['slug'] for agent in data}
print('PINNED_STAGE_AGENTS=' + str(len(data)))
print('GENERATED_PLUGIN_FILES=' + ','.join(sorted(p.name for p in root.iterdir())))
wanted = ('sre-site-reliability-engineer','multi-agent-systems-architect','game-designer','performance-benchmarker','backend-architect','test-automation-engineer')
for slug in wanted:
    print('CATALOG_SLUG_' + slug + '=' + ('PRESENT' if slug in slugs else 'MISSING'))
if not set(wanted).issubset(slugs):
    raise SystemExit('Pinned catalog missing required canonical role slugs')
spec = importlib.util.spec_from_file_location('agency_router_generated', root / '__init__.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
class FakeContext:
    def __init__(self):
        self.tools = {}
    def register_tool(self, **kwargs):
        self.tools[kwargs['name']] = kwargs
ctx = FakeContext()
mod.register(ctx)
expected = {'agency_agents_search','agency_agents_inspect','agency_agents_load','agency_agents_delegate'}
assert set(ctx.tools) == expected
assert all(x['schema']['name'] == name and x['schema']['parameters']['type'] == 'object' for name,x in ctx.tools.items())
search = json.loads(ctx.tools['agency_agents_search']['handler']({'query':'game', 'limit':2}))
assert search['success'] and 0 < len(search['results']) <= 2
slug = search['results'][0]['slug']
inspect = json.loads(ctx.tools['agency_agents_inspect']['handler']({'slug':slug}))
assert inspect['success'] and 'body' not in inspect
print('DYNAMIC_CONTEXT_TOOLS=' + str(len(ctx.tools)))
print('DYNAMIC_SEARCH_INSPECT=PASS')
print('DELEGATE_NOT_INVOKED=TRUE')
PY
echo DISPOSABLE_STAGE_VALIDATION_COMPLETE
INNER_ATLAS_STAGE
echo "DISPOSABLE_CONTAINER_EXIT:$?"
'@
$remote = $remote.Replace("__STAGE_B64__", $stage64).Replace("__VALIDATOR_B64__", $validator64)
$outDir = Join-Path $project ".atlas\opencode\tmp"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$log = Join-Path $outDir "cpaa6-core-disposable-stage.log"
$ErrorActionPreference = "Continue"
$messages = @($remote | & $ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes core-auto bash -s 2>&1)
$sshExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
$lines = @($messages | ForEach-Object { [string]$_ })
$lines | Set-Content -LiteralPath $log -Encoding UTF8
$valid = $sshExit -eq 0 -and ($lines -match "STAGE_VALIDATED") -and ($lines -match "STAGE_READY source=f99f6aa910a442b0197b768ce0ea7751e35e2060") -and ($lines -match "DISPOSABLE_STAGE_VALIDATION_COMPLETE") -and ($lines -match "DISPOSABLE_CONTAINER_EXIT:0")
[pscustomobject]@{
  scope = "disposable_core_staging_only"
  status = $(if ($valid) { "validated" } else { "failed" })
  ssh_exit = $sshExit
  agent_count = $(($lines | Select-String '^PINNED_STAGE_AGENTS=([0-9]+)' | Select-Object -Last 1).Matches.Groups[1].Value)
  log = $log
  production_activated = $false
  backup_dr_certified = $false
} | ConvertTo-Json -Depth 3
if (!$valid) { exit 2 }
