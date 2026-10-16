# Atlas 4.0 — Agency Agents local implementation evidence (2026-10-12)

## Scope
Code-only integration on x99 in the existing `DevEx-HomeLab` tree and current branch `atlas/v0.4.0-proprioception-autonomy`. No worktree or parallel branch created, no live service modified.

## Findings
- Initial branch HEAD `6c6bbba`, ahead 15 of origin. Existing Agency implementation plan was untracked.
- No authenticated SSH to Pentium/core through Remote Desktop Commander; only x99 online.
- Connected GitHub integration could not read the private Issue #11 (404); Backup/DR P0 closure is **unverified**.
- As-built audit 2026-10-10: `self_healing_v1=false`, CP-H12 physical certification pending, exact CONTROL allowlists empty.
- The official agency-agents Hermes integration is a lazy plugin exposing search/inspect/load/delegate. Pinned upstream SHA `f99f6aa910a442b0197b768ce0ea7751e35e2060`; installation not attempted.

## Delivered code (not deployed)
- `infrastructure/pentium/atlas/agency_specialists.py`: versioned config, strict READ-only and scope checks, bounded specialist requests, structured reports, Hermes core worker adapter, counters, optional safe memory/event reuse.
- `infrastructure/pentium/atlas/config_agency_specialists.json`: OFF by default; `worker_host=core`, isolated profile `atlas-specialists`.
- `infrastructure/pentium/atlas/agency_worker_cli.py`: bounded one-shot core-side CLI with fail-closed host/flag gates.
- `infrastructure/pentium/atlas/capability_registry.py`: new opt-in `task_specialist_review` READ capability.
- `infrastructure/pentium/atlas/task_capability_executor.py`: delegates only via injected gateway, default `None` returns `agency_disabled`.
- `infrastructure/core/agency-agents/stage-hermes-router.sh`: pinned isolated staging, no live plugin write.
- `tests/test_agency_specialists.py`, `test_agency_task_bridge.py`, `test_agency_worker_cli.py`, `test_agency_scenarios.py`: fail-closed contract, schema, memory redaction, worker isolation, all three projects in mocks.

## Test evidence
1. RED: module missing, test collection failed as expected.
2. First GREEN: 13 passed.
3. READ capability bridge GREEN: 17 passed.
4. Initial full regression: `1037 passed, 3 skipped, 42 subtests passed` in 26.39s. This was before adding core CLI and simulated scenarios.
5. With core CLI: targeted `22 passed`.
6. Simulated scenario tests: `4 passed, 3 subtests passed`.
7. Final full regression after core CLI, scenario fixtures and production safeguards: `1046 passed, 3 skipped, 45 subtests passed` in 24.36s, exit code 0 (2026-10-12).
8. `git diff --check` exited successfully. Current branch preserved, ahead 15 of remote; no push, commit, branch switch or worktree made.

## Checkpoint matrix
| CP | State | Meaning |
|----|-------|---------|
| AA0 | BLOCKED | P0 backup/restore + physical CP-H12 unverified |
| AA1 | LOCAL STAGED | Pinned staging script and manifest check ready; core not inspected |
| AA2 | LOCAL GREEN | Typed specialist gateway integrated into existing task executor; no live transport |
| AA3 | LOCAL GREEN | Default-deny READ capability, isolated config, no CONTROL paths |
| AA4 | LOCAL GREEN | Lazy routing prompt/selection budget implemented; remote delegate unverified |
| AA5 | LOCAL GREEN | Snapshot, events, optional MemoryStore; no new task DB or memory graph |
| AA6 | LOCAL GREEN (MOCKS) | unit/integration fixtures across three projects; no live E2E |
| AA7 | HOLD | No production rollout before prerequisites |

## Explicit non-claims
- No actual agency agent delegated on the real core.
- No Hermes plugin installed or enabled in production.
- No graph migration, service restart, Git push, auto-deploy or privilege widening.
- Backup/DR P0 and CP-H12 remain unverified; cannot claim full completion.

## CP-AA3 security follow-up, 2026-10-12 (x99 only)
- OpenCode task `20261013T021806Z-f98b61b9` delivered its own report in `.atlas/opencode/outbox`; status `reported`.
- TDD RED: new synthetic credential tests initially failed, then passed after changing only the `_SECRET` regex in `agency_specialists.py`.
- Corrected persisted episodic memory summary redaction for `sk-` and `sk-proj-` while preserving legacy patterns. Three new tests in `test_agency_specialists.py`, now 16 for that module.
- Independent full regression: `1049 passed, 3 skipped, 45 subtests passed` in 25.69s (x99); `git diff --check` clean.
- Does not establish end-to-end production safety or authorization to enable feature flags.

## CP-AA5 bounded telemetry follow-up, 2026-10-12 (x99 only)
- OpenCode task `20261013T022137Z-702bce13`, session `ses_eccef247affeC1m6LRidwljJ4l`, wrote the matching outbox report and was reconciled to `reported` without resending.
- TDD RED/GREEN expanded `AgencyGateway.snapshot()` with `worker_attempts`, `last_worker_duration_ms`, `worker_duration_total_ms` and bounded code-defined `failure_reasons`. Existing snapshot keys remain.
- Only actual worker invocations count as attempts; blocked requests do not. `time.monotonic()` is used for durations; no request body, secrets, tokens, CPU or cost guesses are persisted.
- Added seven telemetry-focused tests; module now `23 passed`.
- Independent full regression: `1056 passed, 3 skipped, 45 subtests passed` in 23.75s (x99); this includes both `infrastructure/pentium/atlas/tests` and `infrastructure/pentium/agent/tests`.
- RED debugging identified and corrected an accidental missing `_RESULT_KEYS` constant and invalid fixture assumptions before GREEN; the final suite confirms those regressions were resolved.
- No production activation, core-side Hermes plugin execution, Backup/DR certification or physical acceptance occurred. CP-AA0 and CP-H12 remain blocking.

## CP-AA1 pinned Hermes staging preflight follow-up, 2026-10-12 (x99 only)
- OpenCode was invoked through the private Tailscale API and project inbox for tasks `20261013T023608Z-b9700aef` and `20261013T024026Z-db860b59`; both sessions were interrupted after stalling, with no delivered agent report. They produced an initial validator/test draft. Orchestrator repaired and validated that draft independently. Do not attribute this final GREEN result to a completed OpenCode report.
- `infrastructure/core/agency-agents/plugin_validator.py`: fail-closed static stdlib validator of the exact generated path `STAGE/source/integrations/hermes/agency-agents-router`, manifest name/four unique tools, regular bounded files, unique agent slugs, pinned generator metadata fields, invalid JSON, traversal and symlinks. Does not import or execute generated plugin Python.
- `infrastructure/core/agency-agents/stage-hermes-router.sh` now invokes the validator after conversion; pinned upstream SHA unchanged and no live Hermes installation/enabling.
- `py -m unittest discover -s infrastructure/core/agency-agents -p test_plugin_validator.py -q`: 13 tests, 12 passed and 1 skipped (Windows symlink privilege unavailable). Static Bash syntax: `C:\Program Files\Git\bin\bash.exe -n` exit 0.
- Independent canonical regression: `1056 passed, 3 skipped, 45 subtests passed` in 25.12s. `git diff --check` clean.
- **Still not verified:** plugin generation on a real isolated Linux core container, upstream runtime dynamic plugin compatibility, physical CP-H12, Issue #11 Backup/DR, permissions, CPU/RAM benchmark and live E2E. The local Docker daemon on x99 is offline; no production flags, services, Git remote or branches changed.

## CP-AA2 worker boundary hardening, 2026-10-12 (x99; OpenCode over private VPN)
- OpenCode task `20261013T025137Z-a0a8986b`, session `ses_eccd3ade6ffeueE9HwLQmvXTGL`, completed with matching outbox report and `reported` status.
- In `agency_worker_cli.py`, removed the `ATLAS_CORE_STAGING_CONTAINER` env-var bypass for non-core hosts. `host != "core"` now fails closed regardless of environment. Actual host attestation in an isolated core container remains an open deployment prerequisite; hostname checks alone are not cryptographic attestation.
- Core CLI now validates returned worker data using `AgencyResult.from_worker()`, rejects unexpected action fields and invalid statuses, emits only a strict result mapping, and checks serialized output-size budget before returning. Existing `main()` fail-closed guard retained.
- TDD RED to GREEN with expanded `test_agency_worker_cli.py`: 11 focused tests passed; independent canonical regression `1062 passed, 3 skipped, 45 subtests passed` in 24.01s. `git diff --check` exit 0.
- No physical transport, plugin activation, workflow promotion or production changes.
- A follow-on CP-AA4 local selection task `20261013T025806Z-f8b60dcf` was started but interrupted because the agent stalled after file reads. It made no selector/module/test changes and delivered no outbox report. CP-AA4 remains NOT implemented.

## CP-AA4 bounded specialist selector follow-up (x99, 2026-10-13)
- OpenCode task `20261013T030843Z-eff1b421` completed and delivered matching outbox report (`reported`), creating `infrastructure/pentium/atlas/agency_specialist_selector.py` and five initial tests in `test_agency_specialist_selector.py`.
- The first version used project roles only and did not inspect objective semantics. Additional RED tests were left by an interrupted OpenCode task `20261013T031138Z-31847ea8`; the retry `20261013T031446Z-afce2ea2` also stalled. A third narrowly scoped OpenCode retry `20261013T031759Z-cdd17ba5` was interrupted with no report. None was counted as completed.
- The orchestrator applied a minimal local GREEN correction: fixed project-specific PT-BR/English whole-word keyword matching against bounded `objective`, never against untrusted candidate descriptions; irrelevant objectives abstain; at most two deterministic available role slugs are returned; bool `max_agents` rejected. No runtime wiring or permissions granted.
- Focused selector TDD: `14 passed`. Independent canonical regression: `1076 passed, 3 skipped, 45 subtests passed` in 30.15s; `git diff --check` exit 0.
- CP-AA4 local selector module is validated. The real Hermes catalog search, plugin integration, worker transport and core execution are not validated. Production feature toggle remains `enabled: false`.

## CP-AA4.2 selector-to-task integration, 2026-10-13 (x99, local-only)
- OpenCode task IDs `20261013T032342Z-033af702` and `20261013T032729Z-0c7ad214` were initiated through the Tailscale VPN with project-scoped inbox; both stalled during read/search and were interrupted. Both statuses are `agent_interrupted`; neither delivered a report or modified these source files. Do not attribute the completed integration to these OpenCode sessions.
- Orchestrator implemented a narrow opt-in bridge in `task_capability_executor.py`: `specialist='auto'` uses **only** a constructor-injected `specialist_candidate_provider(project, objective)`, the existing `select_specialists` pure selector, and the canonical `AgencyRequest` to dispatch to the existing `AgencyGateway`. Manual `specialist` behavior remains compatible.
- Fail closed before consulting provider unless SelfWork is WORKING, the gateway feature is explicitly enabled, the project is allowlisted, the request is valid/bounded/unexpired, the agent budget is 1-2, and a trusted provider is callable. Empty/invalid/rejected candidates, provider errors and paused tasks do not dispatch. Only slugs present in supplied bounded candidate metadata may be selected; task params cannot supply candidates; errors do not echo credentials or raw model output.
- TDD started RED with `8 failed, 5 passed`; GREEN: `14 passed, 2 subtests passed` for `test_agency_task_bridge.py`, including a local-only real AgencyGateway + fake worker scenario, policy default-deny and no command execution. Independent final regression: `1086 passed, 3 skipped, 47 subtests passed` in 24.16s; `git diff --check` clean.
- CORE probe from x99: Tailscale ping via DERP(sao) to `100.97.105.116` succeeded, TCP 22 was reachable, but noninteractive strictly verified SSH did not authenticate (exit 255). No remote command, dynamic Hermes plugin staging, direct core worker test, prod activation or physical Backup/DR verification was performed. `agency_specialists.enabled=false` unchanged.
- Core Hermes catalog candidate provider is **not implemented** and must be explicitly trusted and supplied; no file, network or agent catalog discovery was added. Actual live review remains disabled by policy and config.

## CP-AA6 disposable core staging and LOCAL E2E (2026-10-13)
- Git OpenSSH (not the broken Windows system ssh.exe) authenticated from x99 to `core` and `pentium` with preexisting keys and strict host-key verification. Read-only pentium inventory found four Atlas user units active; the checkout is detached/dirty. P0 Backup/DR restore and full CP-H12 remain blocked.
- Created repeatable `tools/atlas-cpaa6-stage-core.ps1`: on core, `docker run --rm` with pinned cached image ID, no bind mounts/secrets/ports, non-root user, read-only rootfs, all capabilities dropped, network only for pinned Git fetch, resource quotas and ephemeral tmpfs. No production installation.
- Core disposable stage generated 282 agents from pinned upstream `f99f6aa910a442b0197b768ce0ea7751e35e2060`; static validator accepted manifest/4 tools. Fake-context dynamic registration of 4 exact schemas plus search/inspect passed. Actual delegate was never invoked.
- Real pinned catalog revealed `sre` and `backend-engineer` absent; present canonical roles are `sre-site-reliability-engineer` and `backend-architect`. Local selector was updated to prefer real slugs, use legacy only if explicitly supplied, and never duplicate a logical role.
- OpenCode task `20261013T033933Z-12de387f` produced a 14-test offline E2E suite and late report; status reconciled `reported`. OpenCode task `20261013T035007Z-e89ef208` modified selector/test files but timed out and was interrupted without report; independent validation and corrections obtained final GREEN.
- Focused selector+E2E: `36 passed, 6 subtests passed`. Full canonical regression: `1108 passed, 3 skipped, 53 subtests passed`; static validator: `12 passed, 1 skipped`; API bridge: `11 passed`; git diff check clean.
- Complete physical as-built: `docs/as-built/2026-10-13-atlas-cpaa6-disposable-core.md`. Log: `.atlas/opencode/tmp/cpaa6-core-disposable-stage.log`. Live feature flags and effective Hermes plugin permissions were not changed.

## CP-DR11 security hardening and backup image packaging (2026-10-13)
- Authenticated inventory proved Restic binary, backup timer, `/etc/homelab/backup.env` and Restic key absent on both Pentium and Core. P0 Issue #11 remains BLOCKED.
- Repaired unsafe `restic-verify.sh` arbitrary-path deletion with owned isolated child/temp cleanup, strictly validated snapshot date/tag and SQLite integrity. 13 Linux fake-restic adversarial tests passed on disposable Core.
- Real Restic 0.17.3 engine created/restored an **entirely synthetic** SQLite snapshot in isolated disposable Core container; sentinel preserved and integrity passed. This is not a restore of real production backups.
- Fixed declarative backup image packaging: pinned Dockerfile includes Restic + Python + SQLite + curl + required scripts, Compose now fail-closed for env mounts/secrets with non-root/read-only/no caps. Temporary Core image build and Compose config lint passed. Offsite and live backup unconfigured.
- Regression remains `1108 passed, 3 skipped, 53 subtests passed`; backup static suite `11 passed, 13 POSIX skipped on Windows`, with 13 POSIX tests separately passed in Core. `git diff --check` clean.
- Details: `docs/as-built/2026-10-13-atlas-dr11-recovery-hardening.md`. Safe reproductions: `tools/atlas-dr11-test-core.ps1`, `tools/atlas-dr11-real-restic-core.ps1`, `tools/atlas-dr11-build-core.ps1`.
- OpenCode task `20261013T040959Z-c653cd9a` stalled after reading files and was interrupted without a report; implementation completed by orchestrator, not by that agent.

## Next safe action
Fix the unsafe init/unlock and SQLite transaction consistency in `restic-backup.sh` with TDD; provision approved encrypted backup repository/offsite/secret paths and prove **real data restoration** before Issue #11 or CP-H12 can be certified. Then authorize isolated Core Hermes profile/typed transport and READ-only subagent smoke. Keep `enabled: false`, default-deny policy and all live services unchanged.
