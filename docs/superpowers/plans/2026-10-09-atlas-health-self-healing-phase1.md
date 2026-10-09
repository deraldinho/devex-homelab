# Atlas Health Supervisor + Self-Healing Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a canonical multi-host health supervisor and safe self-healing loop for Pentium, x99 and core that distinguishes process liveness from functional health, revalidates action assumptions, and never reports recovery without independent verification.

**Architecture:** Add a standalone health-supervisor runtime above existing health/observation components. It consumes typed functional probes and existing managed-host infrastructure, persists one canonical health snapshot, plans only typed allowlisted recoveries, revalidates decision preconditions immediately before execution, and verifies postconditions independently. Existing `health_engine`, `PolicyCapabilities`, `SafeLocalCapabilityExecutor`, `ManagedReadService`, `ManagedControlService`, Discord, cognition and observation remain compatible.

**Tech Stack:** Python 3, dataclasses/enums, SQLite/JSON runtime state, systemd --user, existing bounded SSH transport, pytest/unittest, Docker CLI only through typed allowlisted operations.

**Spec:** `docs/superpowers/specs/2026-10-09-atlas-health-self-healing-memory-coherence-autonomy-design.md`

## Global Constraints

- Preserve all existing Atlas behavior and public interfaces unless explicitly extended with backward-compatible defaults.
- No generic shell capability and no LLM-generated command execution path.
- READ may auto-run only when allowlisted.
- Reversible CONTROL may auto-run only when allowlisted and within cooldown/action budgets.
- DESTRUCTIVE or potentially irreversible actions always require explicit human confirmation.
- Memory or retrieved text never grants authorization.
- Every autonomous recovery requires independent closed-loop functional verification.
- Remote control uses the existing managed inventory + bounded SSH transport; do not create a second SSH implementation.
- Feature rollout must be independently disableable.
- SQLite/config migrations are additive only.
- Do not restart unrelated Atlas services during rollout.
- TDD: observe RED before production code, then GREEN, then run the complete Atlas suite before promotion.
- No guessed remote targets: x99/core CONTROL targets come only from verified managed inventory allowlists.

## Review Focus

- Process is `active` but its functional probe is disconnected/stale: supervisor must not classify HEALTHY.
- A snapshot or evidence record is older than its freshness bound: recovery must refresh/reprobe before acting.
- x99/core becomes unreachable between planning and execution: action must fail closed without consuming success state.
- Duplicate/concurrent recovery requests target the same host/component: only one valid recovery attempt may execute within policy/cooldown.
- A destructive action was planned earlier but confirmation/preconditions changed: execution must revalidate and refuse stale authorization.

---

## File Structure

**Create**
- `infrastructure/pentium/atlas/health_supervisor_model.py` — canonical health types and compatibility mapping.
- `infrastructure/pentium/atlas/health_supervisor.py` — aggregation, state derivation and atomic snapshot/event publishing.
- `infrastructure/pentium/atlas/health_probes.py` — functional probe contracts and Atlas component probes.
- `infrastructure/pentium/atlas/host_adapters.py` — Pentium/x99/core read-only adapter facade over existing managed infrastructure.
- `infrastructure/pentium/atlas/recovery_model.py` — typed recovery plans/results/risk metadata.
- `infrastructure/pentium/atlas/decision_preconditions.py` — capture and revalidation of execution assumptions.
- `infrastructure/pentium/atlas/recovery_controller.py` — plan/execute/verify/escalate state machine.
- `infrastructure/pentium/atlas/health_supervisor_daemon.py` — periodic owner loop.
- `infrastructure/pentium/atlas/config_health_supervisor.json` — supervisor targets, expected states and feature flags.
- `infrastructure/pentium/atlas/atlas-health-supervisor.service`
- focused tests named below.

**Modify**
- `infrastructure/pentium/atlas/capability_registry.py`
- `infrastructure/pentium/atlas/policy_capabilities.py`
- `infrastructure/pentium/atlas/autonomy_executor.py`
- `infrastructure/pentium/atlas/cognitive_daemon.py`
- `infrastructure/pentium/atlas/discord_gateway.py`
- `infrastructure/pentium/dashboard/dashboard_collectors.py`
- `infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py`
- `infrastructure/pentium/atlas/install-user.sh`
- `infrastructure/pentium/agent/managed_inventory.py`
- `infrastructure/pentium/agent/managed_control.py`
- `infrastructure/pentium/agent/config.json`
- existing packaging/wiring tests.

### Task 1: CP-H1 Canonical health state model and compatibility adapter

**Files:**
- Create: `infrastructure/pentium/atlas/health_supervisor_model.py`
- Test: `infrastructure/pentium/atlas/tests/test_health_supervisor_model.py`
- Existing compatibility reference: `infrastructure/pentium/atlas/state_model.py`

**Interfaces:**
- Consumes: `TechnicalState` from `state_model.py`.
- Produces: `ComponentHealthState`, `HealthDimension`, `ComponentHealth`, `map_technical_state(state: TechnicalState) -> ComponentHealthState`.

- [ ] **Step 1: Write failing model tests**

Tests must assert:
- enum contains exactly `HEALTHY, DEGRADED, STALE, DISCONNECTED, FAILED, RECOVERING, PAUSED_INTENTIONALLY, UNKNOWN`;
- `ComponentHealth` requires component id, host, expected state, four health dimensions, observed timestamp and evidence refs;
- timestamps require timezone;
- `TechnicalState.HEALTHY/ACTIVE/RECOVERED -> HEALTHY`;
- `BUSY/DEGRADED/STRESSED -> DEGRADED`;
- `CRITICAL -> FAILED`.

- [ ] **Step 2: Run RED**

Run:
`python -m pytest infrastructure/pentium/atlas/tests/test_health_supervisor_model.py -q`

Expected: FAIL because `health_supervisor_model` does not exist.

- [ ] **Step 3: Implement minimal model**

Implement:
`class ComponentHealthState(str, Enum)`
`@dataclass(frozen=True) class HealthDimension`
`@dataclass(frozen=True) class ComponentHealth`
`def map_technical_state(state: TechnicalState) -> ComponentHealthState`

Do not modify `TechnicalState`.

- [ ] **Step 4: Run focused GREEN and legacy health tests**

Run:
`python -m pytest infrastructure/pentium/atlas/tests/test_health_supervisor_model.py infrastructure/pentium/atlas/tests/test_health_engine.py -q`

Expected: all pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/health_supervisor_model.py infrastructure/pentium/atlas/tests/test_health_supervisor_model.py`
`git commit -m "feat(atlas): add canonical supervisor health model"`

### Task 2: CP-H2 Health aggregation and canonical persistence

**Files:**
- Create: `infrastructure/pentium/atlas/health_supervisor.py`
- Test: `infrastructure/pentium/atlas/tests/test_health_supervisor.py`

**Interfaces:**
- Consumes: `ComponentHealth`.
- Produces: `AtlasHealthSupervisor.evaluate(components, now) -> SupervisorSnapshot`, `SupervisorSnapshot.to_dict()`, `HealthSnapshotPublisher.publish(snapshot) -> dict`.

- [ ] **Step 1: Write failing aggregation tests**

Pin these rules:
- expected paused component becomes `PAUSED_INTENTIONALLY`, not FAILED;
- process active + functional disconnected => `DISCONNECTED`;
- functional good + stale freshness => `STALE`;
- dependency failed => at least `DEGRADED`;
- all dimensions healthy => `HEALTHY`;
- previous problem -> healthy emits one recovered transition event;
- snapshot writer uses temporary file + `os.replace`;
- repeated identical state does not append duplicate transition;
- malformed/unknown optional component cannot falsely improve aggregate health.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_health_supervisor.py -q`

Expected: FAIL on missing supervisor classes.

- [ ] **Step 3: Implement aggregation and publisher**

Implement:
`@dataclass(frozen=True) class SupervisorSnapshot`
`class AtlasHealthSupervisor:`
`    def evaluate(self, components: tuple[ComponentHealth, ...], now: str) -> SupervisorSnapshot`
`class HealthSnapshotPublisher:`
`    def __init__(self, snapshot_path: Path, events_path: Path, max_events: int = 256)`
`    def publish(self, snapshot: SupervisorSnapshot) -> dict`

Runtime files:
- `atlas/runtime/health-supervisor.json`
- `atlas/runtime/health-events.jsonl`

- [ ] **Step 4: Run focused GREEN**

`python -m pytest infrastructure/pentium/atlas/tests/test_health_supervisor.py infrastructure/pentium/atlas/tests/test_health_engine.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/health_supervisor.py infrastructure/pentium/atlas/tests/test_health_supervisor.py`
`git commit -m "feat(atlas): aggregate canonical component health"`

### Task 3: CP-H3 Functional probes for Atlas services

**Files:**
- Create: `infrastructure/pentium/atlas/health_probes.py`
- Test: `infrastructure/pentium/atlas/tests/test_health_probes.py`
- Modify: `infrastructure/pentium/atlas/discord_gateway.py` only if the existing `discord-gateway-health.json` schema needs a backward-compatible reader field.

**Interfaces:**
- Produces: `ProbeResult`, `FunctionalProbe.probe() -> ProbeResult`.
- Concrete probes: `DiscordGatewayProbe`, `CognitiveSnapshotProbe`, `ObservationJournalProbe`, `DashboardHttpProbe`, `SystemdUserProbe`.

- [ ] **Step 1: Write failing probe tests**

Use temporary files/fake runners. Assert:
- systemd active alone is process evidence only;
- Discord health file with `connected=false` yields disconnected even when process active;
- Discord health older than configured max age yields stale;
- cognitive snapshot older than max age yields stale;
- observation journal not progressing within bound yields stale;
- dashboard HTTP non-2xx/unparseable payload yields degraded/failed probe;
- voice with expected_state=`paused` is not probed as a required running service.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_health_probes.py -q`

Expected: FAIL due to missing probe module.

- [ ] **Step 3: Implement probes with dependency injection**

Exact shared result:
`@dataclass(frozen=True) class ProbeResult:`
`    ok: bool`
`    state: ComponentHealthState`
`    observed_at: str`
`    reason: str`
`    evidence_refs: tuple[str, ...] = ()`
`    metrics: Mapping[str, object] = field(default_factory=dict)`

No network/process call may be hardwired in tests; inject runner/getter/clock.

- [ ] **Step 4: Run GREEN plus Discord regression**

`python -m pytest infrastructure/pentium/atlas/tests/test_health_probes.py infrastructure/pentium/atlas/tests/test_discord_presence_health.py infrastructure/pentium/atlas/tests/test_discord_gateway.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/health_probes.py infrastructure/pentium/atlas/tests/test_health_probes.py infrastructure/pentium/atlas/discord_gateway.py`
`git commit -m "feat(atlas): add functional health probes"`

### Task 4: CP-H4 Multi-host read-only adapter contract

**Files:**
- Create: `infrastructure/pentium/atlas/host_adapters.py`
- Test: `infrastructure/pentium/atlas/tests/test_host_adapters.py`
- Reuse: `infrastructure/pentium/agent/managed_inventory.py`, `managed_read.py`, `ssh_transport.py`

**Interfaces:**
- Produces: `HostObservation`, `HostAdapter.observe(target: str) -> HostObservation`.
- Concrete: `PentiumHostAdapter`, `ManagedHostAdapter`.

- [ ] **Step 1: Write failing adapter tests**

Assert:
- Pentium adapter observes local service without SSH;
- x99/core adapter calls `ManagedReadService`, not subprocess/ssh directly;
- unknown/unmanaged host fails closed;
- remote timeout becomes typed `DISCONNECTED` observation;
- read operation not allowlisted raises/returns denied without fallback shell;
- host adapter output includes host, target, platform, observed_at, evidence and raw status reduction.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_host_adapters.py -q`

Expected: missing module.

- [ ] **Step 3: Implement adapters**

`ManagedHostAdapter` accepts `ManagedInventory` and `ManagedReadService`; no new SSH code.

- [ ] **Step 4: Run GREEN plus managed-agent tests**

`python -m pytest infrastructure/pentium/atlas/tests/test_host_adapters.py infrastructure/pentium/agent/tests/test_managed_inventory.py infrastructure/pentium/agent/tests/test_managed_read.py infrastructure/pentium/agent/tests/test_ssh_transport.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/host_adapters.py infrastructure/pentium/atlas/tests/test_host_adapters.py`
`git commit -m "feat(atlas): add typed multi-host health adapters"`

### Task 5: CP-S1 Recovery model and capability extensions

**Files:**
- Create: `infrastructure/pentium/atlas/recovery_model.py`
- Test: `infrastructure/pentium/atlas/tests/test_recovery_model.py`
- Modify: `infrastructure/pentium/atlas/capability_registry.py`
- Modify: `infrastructure/pentium/agent/managed_inventory.py`
- Modify: `infrastructure/pentium/agent/managed_control.py`
- Modify tests: `test_m2_control_capabilities.py`, agent managed-control/inventory tests.

**Interfaces:**
- Produces: `RecoveryRisk`, `RecoveryState`, `RecoveryPlan`, `RecoveryResult`.
- Extend capability registry with `restart_container(host, container)`.
- Extend `ManagedHost` with backward-compatible `allowed_containers: frozenset[str] = frozenset()`.
- Extend `ManagedControlOperation` with `RESTART_CONTAINER`.

- [ ] **Step 1: Write failing recovery/capability tests**

Assert:
- recovery plan requires host/target/capability/postconditions and positive max_attempts/cooldown;
- `restart_container` is CONTROL, never generic shell;
- container target must be allowlisted by exact name;
- unknown container is denied;
- existing ManagedHost construction without `allowed_containers` remains valid;
- reboot remains DESTRUCTIVE and confirmation-gated.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_recovery_model.py infrastructure/pentium/atlas/tests/test_m2_control_capabilities.py infrastructure/pentium/agent/tests/test_managed_control.py infrastructure/pentium/agent/tests/test_managed_inventory.py -q`

Expected: failures for missing recovery model/container capability.

- [ ] **Step 3: Implement minimal additive model and managed container control**

Linux command must be generated internally as `docker restart <validated-target>`.
Windows command must be generated internally as `docker restart <validated-target>`.
Target comes from inventory allowlist; never concatenate arbitrary LLM command text.

- [ ] **Step 4: Run GREEN**

Run the same focused command; expect pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/recovery_model.py infrastructure/pentium/atlas/capability_registry.py infrastructure/pentium/agent/managed_inventory.py infrastructure/pentium/agent/managed_control.py infrastructure/pentium/atlas/tests/test_recovery_model.py infrastructure/pentium/atlas/tests/test_m2_control_capabilities.py infrastructure/pentium/agent/tests/test_managed_control.py infrastructure/pentium/agent/tests/test_managed_inventory.py`
`git commit -m "feat(atlas): model typed recoveries and container restart"`

### Task 6: CP-S2 Decision preconditions and host-scoped autonomy policy

**Files:**
- Create: `infrastructure/pentium/atlas/decision_preconditions.py`
- Test: `infrastructure/pentium/atlas/tests/test_decision_preconditions.py`
- Modify: `infrastructure/pentium/atlas/policy_capabilities.py`
- Modify: `infrastructure/pentium/atlas/tests/test_autonomy_policy.py`
- Modify: `infrastructure/pentium/atlas/tests/test_policy_capabilities.py`

**Interfaces:**
- Produces: `DecisionPrecondition`, `PreconditionCheck`, `DecisionPreconditionGate.validate(plan, current_state) -> PreconditionCheck`.
- Extend `PolicyCapabilities.__init__` with optional `auto_service_targets=()` and `auto_container_targets=()` while preserving existing `auto_hosts/auto_services` behavior.

- [ ] **Step 1: Write failing precondition tests**

Required checks:
- target is still unhealthy;
- evidence age is inside bound;
- generation/version token unchanged when supplied;
- capability remains allowlisted;
- equivalent recovery has not already completed;
- cooldown/action budget remains available;
- required human confirmation is present and matches current action;
- any failed precondition returns `allowed=False` with reason and never executes.

Add host-scoping regression: allowing `("pentium","atlas-dashboard.service")` must not allow a same-named service on core.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_decision_preconditions.py infrastructure/pentium/atlas/tests/test_autonomy_policy.py infrastructure/pentium/atlas/tests/test_policy_capabilities.py -q`

Expected: fail on missing gate/new host-scoped constructor behavior.

- [ ] **Step 3: Implement gate and backward-compatible policy extension**

Old constructor calls and old cross-product behavior remain valid when new host-scoped sets are omitted.

- [ ] **Step 4: Run GREEN**

Run focused suite; expect pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/decision_preconditions.py infrastructure/pentium/atlas/policy_capabilities.py infrastructure/pentium/atlas/tests/test_decision_preconditions.py infrastructure/pentium/atlas/tests/test_autonomy_policy.py infrastructure/pentium/atlas/tests/test_policy_capabilities.py`
`git commit -m "feat(atlas): revalidate recovery preconditions"`

### Task 7: CP-S3 Multi-host safe-control executors

**Files:**
- Modify: `infrastructure/pentium/atlas/autonomy_executor.py`
- Create: `infrastructure/pentium/atlas/multi_host_executor.py`
- Test: `infrastructure/pentium/atlas/tests/test_multi_host_executor.py`
- Modify: `infrastructure/pentium/atlas/tests/test_autonomy_executor.py`
- Reuse: `infrastructure/pentium/agent/managed_control.py`

**Interfaces:**
- Existing `SafeLocalCapabilityExecutor` remains supported.
- Produce `MultiHostCapabilityExecutor(local_executor, managed_control, inventory, verifier)`.
- `__call__(capability, arguments, plan, action) -> object`.

- [ ] **Step 1: Write failing multi-host executor tests**

Assert:
- Pentium restart routes to existing local executor;
- x99/core service restart routes through `ManagedControlService`;
- remote container restart routes through typed managed control;
- remote host not MANAGED is denied;
- service/container outside per-host allowlist denied;
- reboot without current explicit human confirmation denied;
- command success without functional verification raises `VerificationFailedError`;
- callback/policy execution history records only successfully verified recovery.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_multi_host_executor.py infrastructure/pentium/atlas/tests/test_autonomy_executor.py -q`

Expected: missing multi-host executor.

- [ ] **Step 3: Implement routing without duplicating SSH/control policy**

Use `SafeLocalCapabilityExecutor` for Pentium and `ManagedControlService.execute(ControlAuthorization(...))` for x99/core.

- [ ] **Step 4: Run GREEN plus agent control tests**

`python -m pytest infrastructure/pentium/atlas/tests/test_multi_host_executor.py infrastructure/pentium/atlas/tests/test_autonomy_executor.py infrastructure/pentium/agent/tests/test_managed_control.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/autonomy_executor.py infrastructure/pentium/atlas/multi_host_executor.py infrastructure/pentium/atlas/tests/test_multi_host_executor.py infrastructure/pentium/atlas/tests/test_autonomy_executor.py`
`git commit -m "feat(atlas): execute verified controls across managed hosts"`

### Task 8: CP-S4 Recovery controller, verification and escalation

**Files:**
- Create: `infrastructure/pentium/atlas/recovery_controller.py`
- Test: `infrastructure/pentium/atlas/tests/test_recovery_controller.py`

**Interfaces:**
- Consumes: `RecoveryPlan`, `DecisionPreconditionGate`, policy evaluator, multi-host executor, functional verifier.
- Produces: `RecoveryController.recover(plan: RecoveryPlan) -> RecoveryResult`.

- [ ] **Step 1: Write failing recovery-state tests**

Assert lifecycle:
`PLANNED -> AUTHORIZED -> EXECUTING -> VERIFYING -> RECOVERED`.

Failure cases:
- policy deny => BLOCKED;
- stale precondition => REFRESH_REQUIRED, no execution;
- executor command failure => FAILED;
- command success + failed functional postcondition => FAILED;
- max attempts reached => ESCALATED;
- duplicate recovery key within active/cooldown window => BLOCKED/COOLDOWN;
- failed recovery cannot be rendered as recovered;
- successful independent verification produces evidence refs.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_recovery_controller.py -q`

Expected: missing controller.

- [ ] **Step 3: Implement controller**

Keep action planning deterministic; this layer receives typed plans, not free-form LLM text.

- [ ] **Step 4: Run GREEN**

`python -m pytest infrastructure/pentium/atlas/tests/test_recovery_controller.py infrastructure/pentium/atlas/tests/test_decision_preconditions.py infrastructure/pentium/atlas/tests/test_multi_host_executor.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/recovery_controller.py infrastructure/pentium/atlas/tests/test_recovery_controller.py`
`git commit -m "feat(atlas): add verified recovery controller"`

### Task 9: Supervisor daemon, configuration and service packaging

**Files:**
- Create: `infrastructure/pentium/atlas/health_supervisor_daemon.py`
- Create: `infrastructure/pentium/atlas/config_health_supervisor.json`
- Create: `infrastructure/pentium/atlas/atlas-health-supervisor.service`
- Create: `infrastructure/pentium/atlas/tests/test_health_supervisor_daemon.py`
- Modify: `infrastructure/pentium/atlas/install-user.sh`
- Modify/add packaging test: `infrastructure/pentium/atlas/tests/test_health_supervisor_packaging.py`

**Interfaces:**
- `build_owner(config_root, state_dir) -> HealthSupervisorOwner`
- `HealthSupervisorOwner.run_once() -> SupervisorSnapshot`
- feature flag: `health_supervisor_v1`.

- [ ] **Step 1: Write failing daemon/config/packaging tests**

Config must represent:
- Pentium services: observation, cognitive, discord, dashboard expected running; voice expected paused.
- x99/core managed-host observation enabled.
- recovery feature independently switchable from observation.
- explicit freshness/interval values per target.
- systemd unit writes only within Atlas runtime and uses `Restart=on-failure`.
- installer installs/enables new supervisor service without enabling voice.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_health_supervisor_daemon.py infrastructure/pentium/atlas/tests/test_health_supervisor_packaging.py -q`

Expected: missing daemon/unit/config.

- [ ] **Step 3: Implement daemon/config/unit**

Do not wire broad remote CONTROL yet unless inventory has explicit allowlists. Observation can be enabled first; recovery remains governed by capabilities/inventory.

- [ ] **Step 4: Run GREEN and deployment boundary regressions**

`python -m pytest infrastructure/pentium/atlas/tests/test_health_supervisor_daemon.py infrastructure/pentium/atlas/tests/test_health_supervisor_packaging.py infrastructure/pentium/atlas/tests/test_deployment_truth_packaging.py infrastructure/pentium/atlas/tests/test_runtime_permissions_packaging.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

`git add infrastructure/pentium/atlas/health_supervisor_daemon.py infrastructure/pentium/atlas/config_health_supervisor.json infrastructure/pentium/atlas/atlas-health-supervisor.service infrastructure/pentium/atlas/install-user.sh infrastructure/pentium/atlas/tests/test_health_supervisor_daemon.py infrastructure/pentium/atlas/tests/test_health_supervisor_packaging.py`
`git commit -m "feat(atlas): package health supervisor runtime"`

### Task 10: Canonical health consumption by Discord/dashboard and cognitive wiring

**Files:**
- Modify: `infrastructure/pentium/atlas/discord_gateway.py`
- Modify: `infrastructure/pentium/dashboard/dashboard_collectors.py`
- Modify: `infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py`
- Modify: `infrastructure/pentium/atlas/cognitive_daemon.py`
- Modify: `infrastructure/pentium/atlas/tests/test_autonomy_wiring.py`
- Create: `infrastructure/pentium/atlas/tests/test_canonical_health_consumers.py`

**Interfaces:**
- Consumers read `health-supervisor.json` as canonical operational status.
- Existing fallback status logic remains available when feature flag/snapshot is absent.
- Cognitive capability dispatcher receives `MultiHostCapabilityExecutor` only after its construction succeeds.

- [ ] **Step 1: Write failing consumer/wiring tests**

Assert:
- Discord displays supervisor state instead of inferring health from systemd alone when canonical snapshot exists;
- dashboard uses same component states;
- absent/corrupt supervisor snapshot falls back safely to existing behavior;
- cognitive wiring preserves all existing dispatcher executors;
- remote autonomy uses host-scoped policy targets;
- existing test assumption that only Pentium is autonomous is intentionally replaced by tests proving Pentium/x99/core are supported only through managed allowlists;
- voice remains paused.

- [ ] **Step 2: Run RED**

`python -m pytest infrastructure/pentium/atlas/tests/test_canonical_health_consumers.py infrastructure/pentium/atlas/tests/test_autonomy_wiring.py -q`

Expected: fail on absent canonical consumer and old narrow-autonomy assertion.

- [ ] **Step 3: Implement consumers and wiring**

Do not remove existing status code; make supervisor snapshot the preferred source behind feature flag with fallback.

- [ ] **Step 4: Run GREEN plus Discord/action regressions**

`python -m pytest infrastructure/pentium/atlas/tests/test_canonical_health_consumers.py infrastructure/pentium/atlas/tests/test_autonomy_wiring.py infrastructure/pentium/atlas/tests/test_discord_gateway.py infrastructure/pentium/atlas/tests/test_action_execution.py infrastructure/pentium/atlas/tests/test_cognitive_action_runtime.py infrastructure/pentium/dashboard/tests/test_dashboard_collectors.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

Commit the exact consumer files and tests changed in this task:
`git commit -m "feat(atlas): consume canonical health across runtime"`

### Task 11: Managed inventory promotion for approved autonomy C

**Files:**
- Modify: `infrastructure/pentium/agent/config.json`
- Test/modify: `infrastructure/pentium/agent/tests/test_cli.py`, `test_managed_inventory.py`
- Evidence: `docs/as-built/2026-10-09-atlas-managed-recovery-inventory.md`

**Interfaces:**
- Uses read-only discovery from Tasks 4/9.
- Produces explicit per-host `allowed_controls`, `allowed_services`, `allowed_containers` only for targets verified to exist.

- [ ] **Step 1: Capture read-only inventory on Pentium, x99 and core**

Commands/tools must only enumerate services/containers and current states. Save sanitized target names and evidence in the as-built note. Do not change services.

- [ ] **Step 2: Write/adjust failing inventory test for the exact verified allowlists**

Test exact host-scoped targets and assert no wildcard target support.

- [ ] **Step 3: Run RED**

`python -m pytest infrastructure/pentium/agent/tests/test_managed_inventory.py infrastructure/pentium/agent/tests/test_cli.py -q`

Expected: fail because config does not yet contain approved verified targets.

- [ ] **Step 4: Update config with verified reversible targets**

Rules:
- `restart_service` / `start_service` only for verified safe services.
- `restart_container` only for verified safe containers.
- no `reboot_host` auto authorization.
- no wildcard services/containers.

- [ ] **Step 5: Run GREEN and config loader tests**

Same command; expected pass.

- [ ] **Step 6: Commit**

`git add infrastructure/pentium/agent/config.json infrastructure/pentium/agent/tests/test_managed_inventory.py infrastructure/pentium/agent/tests/test_cli.py docs/as-built/2026-10-09-atlas-managed-recovery-inventory.md`
`git commit -m "config(atlas): allow verified reversible multi-host recovery"`

### Task 12: Full regression and physical certification

**Files:**
- Create: `docs/as-built/2026-10-09-atlas-health-self-healing-certification.md`
- No production change unless certification finds a bug; any fix gets its own RED/GREEN cycle.

**Interfaces:**
- Verifies all outputs from Tasks 1-11.

- [ ] **Step 1: Run complete Atlas + managed-agent suites**

Run:
`python -m pytest infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests -q`

Expected: zero failures. Record exact pass/skip/subtest counts.

- [ ] **Step 2: Run git integrity checks**

`git diff --check`
`git status --short --branch`

Expected: no untracked implementation artifacts except deliberate certification doc before commit; no unrelated changes.

- [ ] **Step 3: Deploy only changed Atlas artifacts to Pentium using the existing deployment mechanism**

Before restart, capture PIDs/state for:
- atlas-observation
- atlas-cognitive
- atlas-discord
- atlas-dashboard
- atlas-health-supervisor

Do not restart unrelated services.

- [ ] **Step 4: Start/restart only atlas-health-supervisor and services whose own code changed**

Verify unaffected services retain PIDs where possible.

- [ ] **Step 5: Verify canonical snapshot**

Confirm `health-supervisor.json`:
- four core Atlas services are functionally healthy;
- Discord is connected, not merely process-active;
- voice is `PAUSED_INTENTIONALLY`;
- x99/core observations are current or explicitly DISCONNECTED/DEGRADED with evidence.

- [ ] **Step 6: Controlled fault-injection smoke**

Use only disposable/test-safe targets or a supervisor fake/fixture first. Then perform one real reversible recovery on an explicitly allowlisted non-critical target if available.

Prove:
- fault detected;
- recovery authorized by current policy;
- preconditions revalidated;
- one action executed;
- functional postcondition independently verified;
- no recovery loop;
- event/health snapshot records transition.

Do not use reboot/destructive operations for certification.

- [ ] **Step 7: Confirm destructive gate**

Attempt a dry-run/planned `reboot_host` path without human confirmation and prove policy returns `CONFIRM`/denied execution.

- [ ] **Step 8: Record certification evidence**

Document commands, timestamps, PIDs, component states, fault injected, recovery result, failed-action behavior, and rollback procedure.

- [ ] **Step 9: Final complete suite**

Run again:
`python -m pytest infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests -q`

Expected: zero failures after physical-smoke adjustments.

- [ ] **Step 10: Commit certification**

`git add docs/as-built/2026-10-09-atlas-health-self-healing-certification.md`
`git commit -m "docs(atlas): certify health supervisor and self healing"`

---

## Self-Review Result

**Spec coverage for this plan:** CP-H1, CP-H2, CP-H3, CP-H4, CP-S1, CP-S2, CP-S3 and CP-S4 are covered. Operational Event Log, Memory Lifecycle, Memory Graph v2, Memory Decision Layer, context compaction, persistent goals, resource/model routing, cache optimization and Personal Ops intentionally remain for subsequent plans because they are independently testable subsystems.

**Type consistency:** Supervisor state, probe result, recovery plan/result, decision precondition gate and executor interfaces are defined once and consumed by later tasks. Existing `PolicyCapabilities` and `SafeLocalCapabilityExecutor` remain backward-compatible.

**Safety coverage:** active-but-broken, stale data, remote disconnect, duplicate recovery and stale/destructive authorization are each pinned to explicit tests above.

**Proportion:** The plan specifies interfaces and observable behavior, not implementation bodies. Remote target names are deliberately not guessed; Task 11 binds exact auto-control targets only after read-only discovery proves their existence.
