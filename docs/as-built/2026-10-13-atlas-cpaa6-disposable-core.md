# Atlas CP-AA6 — core disposable staging and local E2E (2026-10-13)

## Decision / status
- **Local TDD and real disposable-core plugin generation: GREEN.**
- **Physical live Hermes subagent E2E and production rollout: HOLD.**
- No live Hermes plugin installation, no production flags enabled, no service restart, no deployment, no commits/push/worktree.

## Core host — authenticated and isolated staging
- Access: x99 -> core over Tailscale via authenticated Git OpenSSH alias `core-auto`, with strict host-key verification and existing `id_ed25519_core_automation` key. Windows built-in `ssh.exe` exited 255 without even printing `-V`; Git OpenSSH worked. No host SSH configuration changed.
- Core host: `core`, Docker 29.1.3, user `deraldinho`; four pre-existing containers remained running.
- Reproducible entrypoint: `tools/atlas-cpaa6-stage-core.ps1`, invoked on x99; output log: `.atlas/opencode/tmp/cpaa6-core-disposable-stage.log` (local, ignored).
- Cached core image `devex/core-homelab-runner:2.337.0`, inspected ID `sha256:189cc2fb326f164e487d51cc0d36b0764504482b2673a21373f35145dd72955c`.
- Container controls: `--rm`, `--pull=never`, `--user 65534:65534`, `--read-only`, no host mounts or Docker socket, no published ports, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--pids-limit=96`, `--memory=768m`, `--cpus=1`, scratch `/tmp` tmpfs. Outbound bridge network used solely for pinned upstream Git clone.
- Executed pinned tool `infrastructure/core/agency-agents/stage-hermes-router.sh` plus `plugin_validator.py` in disposable environment only.
- Pinned upstream `msitarzewski/agency-agents@f99f6aa910a442b0197b768ce0ea7751e35e2060`; LICENSE: MIT.
- Generator result: 282 agents, 4 tools, manifest/catalog verified. `STAGE_VALIDATED` and `STAGE_READY` reported, container returned 0.
- Dynamically imported generated plugin **only inside the disposable container**. A fake context registered exactly `agency_agents_search`, `agency_agents_inspect`, `agency_agents_load`, `agency_agents_delegate`; schema names and parameters were checked. Handler search and inspect read-only smoke passed; **delegate was NOT invoked**, no real Hermes subagent/model/provider tested.
- Canonical pinned slugs confirmed present: `sre-site-reliability-engineer`, `multi-agent-systems-architect`, `game-designer`, `performance-benchmarker`, `backend-architect`, `test-automation-engineer`.
- Physical discovery revealed legacy `sre` and `backend-engineer` were **absent** from the generated catalog. Local selector changed to prefer canonical actual slugs and only use legacy aliases if explicitly supplied by a trusted candidate source; aliases cannot be fabricated from catalog data.

## Pentium — authenticated read-only inventory
- x99 -> `pentium` authenticated through Git OpenSSH and Tailscale with strict host key validation. No command mutated files or systemd.
- User services observed active/running: `atlas-cognitive`, `atlas-dashboard`, `atlas-discord`, `atlas-observation`. `atlas-voice` remained inactive.
- Pentium checkout HEAD short SHA `920de20`; 181 dirty paths and no named branch reported in read-only inventory. This is **not** the x99 development branch state; do not promote/mirror blindly.
- Hermes directory present on Pentium; no successful live worker profile/subagent invocation; effective tool-free preflight/credential scopes were not certified in this run.
- CP-H12 remains **not fully certified**: active unit status alone is not release, health, rollback or restore proof.

## Local software proof
- `infrastructure/pentium/atlas/tests/test_agency_e2e_certification.py` is a LOCAL OFFLINE simulated suite authored by OpenCode, with actual SelfWorkRuntime/Gateway/TCE and fake worker, three projects and adversarial default-deny/invalid outputs/paused/off/cancel scenarios.
- Pin-aware selection regressions extend `test_agency_specialist_selector.py` and use actual catalog slugs. Legacy compatibility is exercised only with explicit on-demand candidates.
- Focused selector + E2E: `36 passed, 6 subtests passed`.
- Final canonical regression: `1108 passed, 3 skipped, 53 subtests passed` in 24.17s.
- Validator unittest: 13 total, 12 passed and 1 skipped due Windows symlink privilege. Atlas/OpenCode bridge unittest: 11 passed. `git diff --check` zero errors.
- OpenCode local E2E task `20261013T033933Z-12de387f` timed out before reporting but delivered late; `reconcile` returned `reported`. Its report was written before physical access was verified and before canonical slug correction, so this as-built takes precedence for current status.
- OpenCode slug compatibility task `20261013T035007Z-e89ef208` made local code changes but timed out and was interrupted without outbox report. Independent tests and review validate current results; do not claim an OpenCode completed report for that task.

## Blockers — HOLD
1. P0 Backup/DR issue #11 and **actual restore test** not certified. Connected GitHub issue fetch returned 404; cannot treat this as resolved.
2. Pentium CP-H12 release provenance, current dirty checkout, preflight 0-tools and rollback plan still require physical security review.
3. Core has no installed host `hermes` command; **no authorized, isolated `atlas-specialists` profile with scoped credentials** has been provisioned. Do not install into live Pentium Hermes.
4. Typed authenticated worker transport and real `agency_agents_delegate` tool / provider-model invocation not tested; fake context does not prove a real Hermes subagent works.
5. No authority granted to relax `PolicyCapabilities`, expand tools, enable `agency_specialists.enabled`, run live game/PDV operations, or deploy services.

**Safe next action:** certify backup/restore and CP-H12, review isolated worker image/profile tool grants, then a tightly scoped real READ-only Hermes smoke on disposable core worker. Keep all production features default-denied.
