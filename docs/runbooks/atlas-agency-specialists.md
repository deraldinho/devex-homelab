# Atlas — Agency Agents / Hermes specialist router runbook
Data: 2026-10-12. Deployment status: HOLD (local code staged only).

## Inventory and ownership
- Source: `msitarzewski/agency-agents`, revision pinned `f99f6aa910a442b0197b768ce0ea7751e35e2060`.
- Source-of-truth of tasks: `SelfWorkRuntime`/`SelfWorkStore` (not another scheduler).
- Source-of-truth of authority: `CapabilityRegistry`, `PolicyCapabilities` and `ActionPolicy`.
- Source-of-truth of memory: `MemoryStore` and existing `MemoryGraph`; summaries only, no raw prompts.
- `HermesAdapter` is preserved; its `atlas` profile is tool-free and retains the 8-field JSON v1 contract.
- `atlas-specialists` is a distinct Hermes profile reserved to a disposable worker on the `core`.
- `agency-agents-router` exposes `agency_agents_search`, `inspect`, `load`, `delegate` lazily.
- The `pentium` must not execute Hermes specialist models, shell, code builds, or staging.

## Shipped feature toggle / boundaries
- `infrastructure/pentium/atlas/config_agency_specialists.json`: `enabled: false` (default).
- `agency_specialists.py`: typed request/result, strict READ-only, max two slugs, response bound, fail-closed, sanitized memory, operational status counters.
- `task_specialist_review` registered READ but deliberately absent from `cognitive_daemon` read_auto_allow (so denied, regardless of LLM claims).
- `TaskCapabilityExecutor(... specialist_gateway=None)`: leaves existing behavior unchanged; an approved owner must inject the gateway after certifying the core transport.
- `agency_worker_cli.py`: one-shot core-only READ worker accepting bounded JSON via stdin, no daemon, task queue, server socket, or arbitrary shell exposed.
- The worker's proposed changes and tests_run are **untrusted specialist claims**; Atlas must independently prove test and policy gates.

## CP-AA0 — mandatory hard gates
1. Verify Issue #11 Backup/DR state in the actual repository and prove restore. The connected GitHub app could not fetch the private issue.
2. Verify Pentium CP-H12 actual systemd status, release identity and service health using authenticated, pinned SSH/managed read. As of 2026-10-13 authenticated x99 -> Pentium and x99 -> core read-only SSH is working via Git OpenSSH with existing keys and strict host-key verification, but complete CP-H12 and Backup/DR restore certification remain pending. See `docs/as-built/2026-10-13-atlas-cpaa6-disposable-core.md`.
3. Audit effective `atlas` preflight (0 tools) and current `self_healing_v1: false`. No broadening allowlists.
4. Record SHA and baseline plus rollback for the actual core worker container, and approve resource budgets. Never assume old local tests equal live success.

## CP-AA1 — isolated staging on core, *not on pentium*
Use the declarative pin from `infrastructure/core/agency-agents/stage-hermes-router.sh`:
```bash
# Run on core (or a dedicated disposable container with ATLAS_CORE_STAGING_CONTAINER=1).
bash infrastructure/core/agency-agents/stage-hermes-router.sh /tmp/atlas-agency-stage-20261012
```
This checks out an exact upstream revision, generates the router and validates a manifest/catalog. It DOES NOT install into real `~/.hermes` and does not restart anything.

Review staged `__init__.py`, `plugin.yaml`, `data/agents.json`, upstream conversion/build/install scripts and all invoked dependencies. Do not run unreviewed upstream install scripts with production credentials.

After CP-AA0 is GREEN, construct an isolated **non-privileged** core worker environment with no production mounts or SSH keys. Its HOME/HERMES_HOME and provider credentials must be scoped to the worker. Create the separate `atlas-specialists` profile and load *only* the vetted router plugin. Keep the old `atlas` profile unchanged.

## CP-AA2 / CP-AA3 — hooking and policy
- An active `SelfWorkRuntime` job with `task_id` is required.
- Set `AgencyConfig.enabled` true **only in the authorized worker/controller rollout** after gates; the repository's default remains false.
- A typed core transport adapter must call the exact one-shot `agency_worker_cli.py` entrypoint via a reviewed pre-existing managed transport; **do not** add arbitrary SSH commands or a new executor.
- Validate HTTPS/mTLS or authenticated typed transport, strict host verification, serialization limits, replay safeguards, and returned schema before bridging the nodes.
- Only then inject `AgencyGateway(config, self_work, worker_transport, memory_store=existing_store, event_sink=existing_journal)` into `TaskCapabilityExecutor`. Keep tool-free `HermesAdapter` untouched.
- Explicitly allowlist `task_specialist_review` by project/scope and only after security review; do not allow blanket READ or auto-CONTROL.
- No live game, payment, host control, deploy or Git mutation by delegated specialists.

## CP-AA4 / CP-AA5 — usage
- Default: 1 specialist; hard cap: 2 specialists per request.
- Search, inspect and delegate lazily; do not enable all specialist skills or alter `skills.external_dirs`.
- `AgencyGateway.snapshot()` yields minimal counts, `agency.specialist.result` event contains task/project/status/agent_count only.
- Successful summaries can use existing `MemoryStore`; failure of memory/event sinks does not change SelfWork state.
- The worker does not write to the existing MemoryGraph directly; graph consumption remains with canonical Atlas memory lifecycle.

## CP-AA6 — tests
```powershell
cd C:\Users\deral\DevEx-HomeLab
py -m pytest -q infrastructure/pentium/atlas/tests/test_agency_specialists.py infrastructure/pentium/atlas/tests/test_agency_task_bridge.py infrastructure/pentium/atlas/tests/test_agency_worker_cli.py infrastructure/pentium/atlas/tests/test_agency_scenarios.py
py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests -q
git diff --check
```
- Validate three fixture scenarios: Atlas status READ, Rei da Laje AI READ, Lanchonete do Guru architecture READ. These are mocked and **not** proof of remote subagent execution.
- Before allowing production use: verify real specialist tool schemas and exact 4 tools in effective `atlas-specialists` prompt-size, test malicious prompt, bounded timeout, wrong agent slug, invalid JSON, quota exhaustion, disabled plugin, worker death, network cut, no privilege escalation.

## CP-AA7 — rollout and rollback
1. Remain HOLD until P0 Backup/DR, CP-H12 and core transport approved.
2. Launch **manual READ-only** job in a disposable core environment. Record verified invocation, outputs, cpu/ram, source pin and resulting summary.
3. Validate every existing Atlas service (observation, cognitive, dashboard, Discord) and zero unauthorized actions.
4. Abort conditions: unexpected tools, >2 agents, excessive memory/CPU, stdout > limit, leaked secrets, malformed response, failed backup, missing health signal.
5. Rollback: disable `AgencyConfig.enabled`, deny `task_specialist_review`, terminate isolated worker, restore worker/profile config from certified backup; DO NOT touch or restart the existing Atlas cognitive profile.

## CP-AA6 staging result (2026-10-13)
- Physical disposable `core` stage can be rerun safely from x99 with `tools/atlas-cpaa6-stage-core.ps1`; it clones only pinned Agency Agents SHA inside a no-mount, non-privileged, resource-limited container and destroys it on exit.
- Verified 282 specialists, all four tool schemas and fake-context registration, read-only search/inspect. No real Hermes model/subagent call or authorization has occurred.
- The six canonical slugs, including `sre-site-reliability-engineer` and `backend-architect`, were confirmed. Legacy `sre` and `backend-engineer` are absent from the actual pinned catalog.
- Full evidence and limitations: `docs/as-built/2026-10-13-atlas-cpaa6-disposable-core.md`.

## Certification note
Local software tests and disposable fake-context plugin tests are not a certification of live Hermes plugin/subagents. **No deployment, new service, rollout, live tool permission, self-healing or production feature enablement has occurred.**
