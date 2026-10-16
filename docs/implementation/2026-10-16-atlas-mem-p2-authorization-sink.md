# Atlas — CP-MEM-P2: coherence enforced at the action-authorization sink

**Date:** 2026-10-16
**Predecessor:** CP-MEM-P1 (`docs/implementation/2026-10-16-atlas-mem-p1-signed-ingress.md`)
**State:** implemented and tested locally on x99; Pentium deployment **HOLD**.

## Verified baseline / rationale

Canonical checkout: `C:\Users\deral\DevEx-HomeLab` on branch
`atlas/v0.4.0-proprioception-autonomy`. `py -m pytest
infrastructure/pentium/atlas/tests` was GREEN (**1415 passed, 8 skipped,
217 subtests**) before any edit. No unrelated file was reset, staged, deployed
or restarted.

CP-MEM-P0/P1 made memory evidence tamper-evident and immutable, but only at
*ingestion, retrieval and promotion*. The decision that actually matters — the
authorization of an action — could still auto-execute a state-changing
capability on the strength of memory evidence whose provenance was never
verified. P2 moves the check to the authorization decision: a capability action
must not be auto-authorized when the memory evidence that influenced the plan is
untrusted or tampered.

## Scope implemented

1. `memory_action_gate.py` (new, stdlib only):
   - `ActionRisk` (LOW/MEDIUM/HIGH) and `classify_risk(level)`. Fail closed:
     `READ -> LOW`, `CONTROL -> MEDIUM`, `DESTRUCTIVE -> HIGH`, **unknown level
     or non-string -> HIGH**.
   - `MemoryCoherenceGate.evaluate(capability, level, memories, *, correlation_id,
     human_approval) -> CoherenceDecision`. It can only **restrict, quarantine or
     escalate** — it never grants authority and never widens what the capability
     policy allowed.
   - `QuarantineRegistry`: durable, bounded (1000 entries) review queue for
     memories flagged as tampered. Atomic write (temp + replace); a corrupt or
     foreign-schema file is ignored, never trusted. This is an operational
     receipt, not a cognitive `MemoryRecord`.
   - `correlation_id` is validated and echoed on every decision for traceability.
2. `action_policy.py` (the authorization sink):
   - `ActionPolicy(capability_policy, *, coherence_gate=None)` — backward
     compatible; without a gate every prior behaviour is unchanged.
   - `authorize(plan, *, voice_enabled=False, evidence=(), correlation_id=None,
     human_approval=False)`. When a gate is configured, capability requests that
     the capability policy would auto-authorize are then checked against the
     memory evidence: a blocked verdict becomes `BLOCKED`
     (`reason="memory_coherence:<code>"`); an escalation verdict becomes
     `AUTHORIZED` with `requires_confirmation=True` instead of auto-executing.
   - `correlation_id` defaults to `plan.plan_id`, so an action is traceable back
     to the plan that produced it even when the caller does not supply one.
3. `foundation-ci.yml`: `memory_action_gate.py` added to the `py_compile` gate.

## Risk and decision model (deterministic, restrict-only)

| Evidence state | LOW (READ) | MEDIUM (CONTROL) | HIGH (DESTRUCTIVE) |
|---|---|---|---|
| none retrieved | allow | allow | allow |
| any tampered | allow + quarantine | **block** + quarantine | **block** + quarantine |
| un-attested (no verified provenance) | allow | **escalate** to human | **escalate** to human |
| all attested | allow | allow | allow |

- Tampering is never overridable: a tampered verdict blocks regardless of
  `human_approval`, and the offending `memory_id`s are quarantined.
- Escalation is resolved only by an explicit `human_approval=True` at the sink;
  until then the action is authorized-with-confirmation, not executed.

## Explicit trust boundary

- The gate is a **policy sink**, not an authority source. It has no memory of its
  own beyond the quarantine queue and cannot elevate a blocked capability.
- Evidence records are read defensively: only `Mapping` items with a valid
  `memory_id` participate; `integrity == "attested"` is the only trusted state,
  `"tampered"` is hostile, everything else (including a missing key) is
  un-attested. There is no path where an unknown integrity value grants trust.
- The default sink path is unchanged until a caller supplies a gate **and**
  evidence, so no live behaviour is altered by this checkpoint.
- The quarantine file is a local operational artifact; its production path,
  retention and review workflow are a separate operational gate. No secret is
  created or read by this checkpoint.

## TDD / Quality Gates

- RED reproduced: with `memory_action_gate.py` absent the P2 suite failed to
  import; with the module present but the sink un-integrated, **4 of 17** P2
  tests failed (`ActionPolicy.__init__() got an unexpected keyword argument
  'coherence_gate'`) while the 13 gate-level tests passed.
- GREEN: `test_memory_action_gate.py` **17/17 passed**.
- Full Atlas suite `infrastructure/pentium/atlas/tests`: **1432 passed,
  8 skipped, 217 subtests passed** (x99, exit 0) — 1415 baseline + 17 new.
- `py -m py_compile` on the two touched modules: exit 0. `git diff --check`: exit 0.
- Static: no `TODO`/`TBD` markers introduced (Foundation CI guard).

## Files touched in this checkpoint

- `infrastructure/pentium/atlas/memory_action_gate.py` (new)
- `infrastructure/pentium/atlas/action_policy.py`
- `infrastructure/pentium/atlas/tests/test_memory_action_gate.py` (new)
- `.github/workflows/foundation-ci.yml`
- `docs/implementation/2026-10-16-atlas-mem-p2-authorization-sink.md` (new)

## Blockers for production and next gates

- No live caller yet feeds retrieved evidence into
  `ActionPolicy.authorize(evidence=..., correlation_id=...)`. The daemon wiring
  (using the correlation ID minted at ingestion and the retriever's
  `integrity`/`authority` fields) must be added and E2E-proven in QA before
  deploy. Nothing is activated by this checkpoint.
- The quarantine review workflow (who clears an entry, and the re-attestation
  path) is a separate operational gate.
- **CP-MEM-P3:** adversarial longitudinal sessions and a poisoning corpus;
  measure false approvals/blocks, contamination, classification drift and token
  cost, including existing semantic data and agent-written files.
- Canary only with real Pentium backup, release gate, rollback rehearsal and
  independent review.
