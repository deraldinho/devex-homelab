# Atlas — Health, Self-Healing, Memory, Coherence and Autonomy Design

Date: 2026-10-09
Status: Proposed for implementation
Branch: atlas/v0.4.0-proprioception-autonomy

## 1. Intent

Evolve Atlas into a persistent operator for the homelab and project estate while preserving all existing behavior. Atlas must observe, diagnose, recover, remember, reason over evidence, and execute reversible corrective actions autonomously across Pentium, x99 and core.

The design is additive. Existing health, observation, cognitive, Discord, memory, task, capability, action-policy, and autonomy components remain valid integration points.

## 2. Non-negotiable constraints

- Do not remove or bypass existing Atlas functionality.
- Preserve backward compatibility of existing runtime files and public behavior unless a migration is explicitly versioned.
- TDD for every behavior change.
- All existing tests must remain green.
- Memory is not authorization.
- LLM output never becomes shell authority.
- READ actions may run automatically when allowlisted.
- Reversible CONTROL actions may run automatically when allowlisted and within policy budgets.
- DESTRUCTIVE or potentially irreversible actions require explicit human confirmation.
- Every autonomous action requires closed-loop verification.
- Repeated recovery must obey cooldown, attempt budget and escalation rules.
- All operational state changes must be explainable from evidence and traceable.

## 3. Existing components to preserve and extend

Current architecture already provides:
- health_engine.py and local_health.py
- stimulus_journal.py
- cognitive_observability.py
- memory_model.py / memory_store.py / memory_manager.py / memory_retriever.py
- episodic segments, evidence and provenance
- continuous_intent.py and task_store.py
- capability_registry.py
- policy_capabilities.py and action_policy.py
- autonomy_executor.py with closed-loop service verification
- Discord gateway and dashboard
- workspace health, cache and token budget components

The new architecture must compose these components rather than fork their responsibilities.

## 4. Target operational pipeline

Sensors / probes / gateways
    -> Canonical Operational Event
    -> AtlasHealthSupervisor
    -> Diagnosis + Evidence Bundle
    -> Recovery Planner
    -> Decision Preconditions
    -> Coherence / Risk Gate
    -> Capability Policy
    -> Host-specific Executor
    -> Closed-loop Functional Verification
    -> Event Journal + Memory + Metrics + Notification

## 5. Health Supervisor

Introduce an AtlasHealthSupervisor as an operational aggregator above existing health sources.

### 5.1 Health states

Canonical component states:
- HEALTHY
- DEGRADED
- STALE
- DISCONNECTED
- FAILED
- RECOVERING
- PAUSED_INTENTIONALLY
- UNKNOWN

These states do not replace TechnicalState immediately. A compatibility adapter maps existing TechnicalState values into supervisor state.

### 5.2 Health dimensions

Each managed component reports:
- process_state
- functional_state
- freshness
- dependency_state
- observed_at
- evidence_refs
- recovery_state
- expected_state

A process being active is insufficient for HEALTHY.

Examples:
- Discord: systemd active + gateway connected + heartbeat fresh + authenticated.
- Cognitive daemon: systemd active + cognitive snapshot fresh + successful loop heartbeat.
- Observation daemon: process active + journal freshness + probe progression.
- Dashboard: process active + HTTP probe + current status payload.
- Docker service: container running + service-specific port or health endpoint.

### 5.3 Expected state

The supervisor must distinguish intentional inactivity from failure. Voice is the initial example: a configured paused service yields PAUSED_INTENTIONALLY, not FAILED.

### 5.4 Health persistence

Publish an atomic runtime snapshot:
atlas/runtime/health-supervisor.json

Also append state transitions to:
atlas/runtime/health-events.jsonl

The snapshot is bounded and replace-atomic. The event journal is append/bounded according to existing Atlas patterns.

## 6. Multi-host adapters

Define a common HostAdapter contract:
- observe()
- diagnose()
- available_recoveries()
- execute_recovery()
- verify()
- rollback() when applicable

Initial adapters:
- PentiumAdapter: systemd --user, local files, local TCP/HTTP probes.
- X99Adapter: managed SSH, Windows services/processes, Docker, TCP/HTTP probes.
- CoreAdapter: managed SSH, systemd, Docker, TCP/HTTP probes.

Adapters return typed data. They do not expose arbitrary shell execution to the LLM.

## 7. Self-healing

Recovery is modeled as a typed action with:
- recovery_id
- host
- target
- capability
- risk_class
- reversible
- preconditions
- expected_postconditions
- max_attempts
- cooldown_s
- timeout_s
- rollback_capability
- evidence_refs

Initial recovery capabilities should extend the existing registry rather than bypass it:
- restart_service
- start_service
- restart_container
- reconnect_gateway
- refresh_probe
- clear_transient_failure
- retry_failed_job

No generic shell capability is introduced.

## 8. Risk policy

Canonical execution classes:
- READ: automatic when allowlisted.
- SAFE_CONTROL: automatic, reversible, narrow scope.
- CONTROL: automatic only when allowlisted, reversible and within budget.
- RISKY_CONTROL: confirmation required.
- DESTRUCTIVE: confirmation required.
- FORBIDDEN: denied.

Existing PolicyCapabilities cooldown and action-budget behavior remains authoritative and is extended to multi-host targets.

Examples requiring confirmation:
- host reboot
- firewall changes
- package/system upgrades
- destructive file operations
- purge
- critical configuration overwrite
- destructive database operations

## 9. Closed-loop verification

Execution success is not command success.

Every recovery defines functional postconditions. The verifier must independently observe those postconditions after execution.

Recovery lifecycle:
PLANNED -> AUTHORIZED -> EXECUTING -> VERIFYING -> RECOVERED
or
PLANNED -> ... -> VERIFYING -> FAILED

Repeated failure transitions the incident to escalation rather than infinite restart loops.

Verification evidence must be independent from the command response wherever possible.

## 10. Canonical operational event log

The existing StimulusJournal remains intact for perception events. Add a typed operational event layer for decisions, recoveries and verification.

OperationalEvent fields:
- event_id
- trace_id
- event_type
- host
- component
- observed_at
- source
- payload_reduced
- evidence_refs
- source_version
- confidence
- immutable_hash

Events are append-only at the logical layer. Derived state may be compacted, but evidence references must survive.

## 11. Memory lifecycle and provenance

MemoryRecord is extended through a versioned schema migration, not a destructive rewrite.

New lifecycle fields:
- valid_from
- valid_until
- supersedes_id
- superseded_by_id
- revoked_at
- verifier
- verified_at
- evidence_refs
- source_event_ids
- uncertainty
- memory_type

Initial memory types:
- POLICY_EXACT
- DECISION
- EPISODIC
- OBSERVATION
- DERIVED
- CACHE

POLICY_EXACT records are never lossy-summarized.

Existing episodic evidence and MemoryProvenance remain supported. New provenance fields supplement them.

## 12. Memory admission and coherence

Retrieval does not imply trust.

Introduce a MemoryDecisionLayer between MemoryRetriever and context projection. It evaluates:
- relevance
- freshness
- provenance
- confidence
- contradictions
- risk of the requested task

Outcomes:
- ACCEPT
- REFRESH
- QUARANTINE
- ABSTAIN
- REJECT

For infrastructure actions, stale or conflicting memory triggers a fresh physical probe before authorization.

## 13. Supersession and conflict model

State-changing memories use explicit supersession relationships.

Examples:
service=down at T1
service=healthy at T2

T2 supersedes T1 for current-state reasoning, while T1 remains part of historical evidence.

Conflicting records without a trusted ordering are not silently merged. They remain visible to the coherence gate.

## 14. Context management

Context is divided into:
- exact pinned policy
- current task/goal state
- recent working context
- retrieved verified memory
- compact episodic summaries
- evidence landmarks

Large or old content can be evicted from the prompt but must retain a landmark to recover the exact source.

Continuous compaction is feature-flagged and benchmarked against threshold compaction before becoming default.

## 15. Lossy observation deduplication

Introduce observation deduplication before context projection, never by modifying canonical evidence.

Requirements:
- deterministic duplicate key
- retrieval-rank perturbation tests
- evidence-recall invariant
- measurable token/prefill reduction

The raw operational/event journal remains intact.

## 16. Persistent goals and planning

Extend ContinuousIntent and SelfWorkStore rather than adding a parallel task engine.

A persistent goal contains:
- goal_id
- objective
- scope
- state
- priority
- prerequisites
- subtasks
- attempts
- current_blocker
- evidence_refs
- last_verified_at
- next_check_at
- completion_criteria

Initial persistent operational goals:
- keep Atlas core services healthy
- keep managed hosts observable
- keep critical containers/services healthy
- maintain memory-store integrity
- maintain backup and disk-health visibility

Goals never imply new permissions. Actions still pass through capability/risk policy.

## 17. Resource and model router

ResourceGovernor observes:
- RAM available
- swap pressure
- CPU load
- disk free/IO pressure where available
- model server health
- active inference count
- queue depth

Model routing classes:
- deterministic/no-LLM
- small local classifier
- standard local reasoning
- high-cost reasoning

Routing decisions must be observable and benchmarkable.

The governor may defer non-urgent work or reduce context, but must not discard canonical evidence.

## 18. Cache architecture

Preserve existing CognitiveCache and workspace cache.

Add telemetry before changing eviction:
- phase
- prefix_hash
- model_id
- tokenizer/config identity
- cache_hit
- cache_miss
- kv_bytes when available
- TTFT
- decode_ms
- tool_wait_ms

Safe default:
- exact-prefix reuse only
- invalidate on model/tokenizer/config mismatch

Phase-aware or action-aware KV retention is experimental behind feature flags.

Cross-model KV reuse is out of scope until correctness is demonstrated.

## 19. Reliability harness

Create deterministic and repeated-run suites.

Fault scenarios:
- process alive but gateway disconnected
- stale health snapshot
- failed restart
- successful command with failed functional postcondition
- concurrent recovery requests
- duplicate action delivery
- host temporarily unreachable
- stale memory conflicting with current probe
- revocation after planning but before execution
- model/process restart
- memory-store restart/recovery
- tool timeout and retry
- container running but service port down

Metrics:
- task success
- first-failure detection
- false recovery success
- stale-memory execution rate
- contradiction detection rate
- action retry/duplicate rate
- recovery latency
- abstention rate
- memory precision/recall
- context tokens
- TTFT
- cache hit ratio
- resource utilization

Non-deterministic agent evaluations run repeated trials with recorded seed/model/config and confidence intervals where meaningful.

## 20. Decision preconditions

Every planned CONTROL/DESTRUCTIVE action captures the assumptions that justify it.

DecisionPrecondition examples:
- target is still unhealthy
- evidence is fresh enough
- expected generation/version unchanged
- capability still allowlisted
- action budget available
- no equivalent recovery already succeeded
- human confirmation still valid when required

Immediately before execution, Atlas revalidates affected preconditions.

A precondition failure causes REFRESH or REPLAN, never blind execution.

## 21. Observability

Every user-visible or autonomous operation receives trace_id.

Trace spans must link:
observation -> diagnosis -> memory/context -> plan -> policy decision -> executor -> verification -> notification

Expose operational metrics to the existing dashboard/Prometheus path where practical.

Discord and dashboard consume the same canonical health snapshot to avoid divergent status reporting.

## 22. Personal Ops layer

After reliability gates are stable, Atlas may maintain operational watch over:
- service availability
- Docker/container health
- disk capacity
- backup freshness
- Git repository state
- pending operational incidents
- certificate/credential expiry metadata where safely observable
- scheduled jobs
- managed-host reachability

Notification policy:
- do not spam routine healthy states
- notify meaningful transitions
- notify failed self-healing
- notify actions requiring confirmation
- summarize recoveries with evidence

## 23. Deployment and feature flags

Each subsystem lands behind an explicit feature flag or configuration gate until its tests and physical smoke pass.

Suggested rollout flags:
- health_supervisor_v1
- self_healing_v1
- operational_event_log_v1
- memory_lifecycle_v1
- memory_decision_layer_v1
- persistent_goals_v1
- resource_router_v1
- kv_telemetry_v1

Default rollout order:
1. Health Supervisor
2. Self-Healing + decision preconditions
3. Operational Event Log
4. Memory lifecycle/provenance
5. Coherence / Memory Decision Layer
6. Persistent Goals
7. Resource + Model Router
8. Personal Ops
9. KV optimization experiments

## 24. Compatibility and migration strategy

- Existing JSON runtime files remain readable during migration.
- SQLite migrations are versioned and tested on copied databases.
- Existing MemoryRecord callers continue working through defaults for new fields.
- Existing capability names retain semantics.
- Existing service units remain valid.
- No voice activation is implied by this project.
- Existing Discord, dashboard, cognition and observation paths remain available while new supervisor state is introduced.
- A failed new subsystem must fail closed or fall back to the existing safe behavior where possible.

## 25. Acceptance gates

A phase cannot be promoted unless:
- focused RED/GREEN regression exists
- complete Atlas suite is green
- git diff/check is clean
- physical smoke passes on intended host(s)
- no unrelated service PID changes unless required
- rollback path is documented
- runtime evidence is captured
- existing behavior remains operational

Additional gates for autonomous recovery:
- destructive actions remain confirmation-gated
- no shell-from-LLM execution path exists
- failed verification cannot be reported as recovery
- cooldown/attempt budget blocks recovery loops
- stale planning assumptions are revalidated before execution

## 26. Implementation checkpoints

CP-H1 Health state model and compatibility adapter.
CP-H2 Supervisor aggregation and atomic snapshot.
CP-H3 Functional probes for Discord/Cognitive/Observation/Dashboard.
CP-H4 Multi-host adapter contracts and read-only probes.
CP-S1 Recovery model and capability extensions.
CP-S2 Decision preconditions and revalidation.
CP-S3 Multi-host safe-control executors.
CP-S4 Closed-loop functional verification and escalation.
CP-E1 Canonical operational event journal.
CP-M1 Memory schema lifecycle/provenance migration.
CP-M2 Supersession/conflict support.
CP-M3 Memory Decision Layer.
CP-C1 Context projection with evidence landmarks.
CP-C2 Observation deduplication and compaction benchmarks.
CP-G1 Persistent goal model extending ContinuousIntent/SelfWork.
CP-R1 Resource governor.
CP-R2 Model router.
CP-K1 Cache telemetry.
CP-K2 Phase/action-aware cache experiment.
CP-O1 Unified agent observability and trace IDs.
CP-P1 Personal Ops watchers and notification policy.
CP-Q1 Fault-injection/reliability certification campaign.

## 27. Rollback philosophy

Each checkpoint must be independently disableable. Runtime state written by a new checkpoint must not prevent the previous runtime from starting.

For schema changes:
- backup physical database before migration
- verify migration on copy first
- migration is additive
- no destructive column/table removal in this project

For service changes:
- deploy only changed artifact(s)
- restart only affected service unless dependency evidence requires more
- verify old services retain their PIDs where they are not part of the rollout

## 28. Success criteria

Atlas is considered to have reached the target architecture when:
- it distinguishes process liveness from functional health
- it can autonomously recover allowlisted reversible failures on Pentium, x99 and core
- destructive or irreversible operations always require explicit confirmation
- every recovery is independently verified
- stale planning assumptions are revalidated before execution
- memory can express provenance, validity and supersession
- conflicting/stale memory cannot silently authorize infrastructure actions
- persistent goals survive restarts
- context and cache optimizations are evidence-driven
- Discord and dashboard report one canonical operational truth
- a reliability campaign demonstrates recovery without uncontrolled loops or silent false-success states
