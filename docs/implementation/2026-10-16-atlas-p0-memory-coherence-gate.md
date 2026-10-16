# Atlas — CP-MEM-P0: coherence gate for memory promotion

**Date:** 2026-10-16  
**Research trigger:** Self-Propagating Misalignment in LLM Agents (Radar P0, 2026-10-16)  
**State:** implemented and tested locally on x99; Pentium deployment **HOLD**.

## Verified baseline / rationale

Canonical checkout: `C:\Users\deral\DevEx-HomeLab` on branch
`atlas/v0.4.0-proprioception-autonomy`. Existing worktree contained unrelated
modified/untracked files. None were reset, staged, committed or deployed.

`MemoryManager._promote_recurrent` previously promoted every EPISODIC memory
with a dedupe key, frequency >= 3 and confidence >= 0.7 without validating
source or information type. `remember()`, `_consolidate_duplicates()` and
`MemoryStore.persist_consolidated()` also merged different claims sharing
a user-controlled dedupe key and could raise confidence/retention flags.

## Scope implemented

1. Added `memory_coherence_gate.py`: conservative typed
   observation/fact/hypothesis/instruction classification from restrictive
   tags. Memory metadata cannot authorize commands. Denies automatic semantic
   promotion from agent/LLM/tool/workspace/web and unknown origins, typed
   instructions/hypotheses, unknown kinds, and common role/policy-overriding
   instructions. Allowed semantic promotion remains **evidence only**.
2. Integrated `review_promotion()` in `MemoryManager._promote_recurrent()`.
   Existing benign operational recurrence remains eligible.
3. Hardened `MemoryManager.remember()` and bulk consolidation: dedupe needs
   matching origin, exact content, entity, layer, kind tags, pinned/protected
   flags and dedupe key. Repetition may increase frequency but not confidence,
   importance, criticality or protection by itself.
4. Hardened episodic persistence in `MemoryStore.persist_consolidated()`
   through `find_matching_claim()`. Distinct episode texts sharing a semantic
   key stay separate; segment-to-memory provenance remains associated with the
   correct record.
5. Retrieval labels explicitly typed records with
   `authority=evidence_only`. The existing Hermes prompt already treats
   retrieved memory as untrusted evidence, not as tool permissions.
6. Added deterministic red/green regression tests, including self-origin
   injection, spoofed tool/workspace claims, unknown kinds, role injection,
   confidence inflation, dedupe-key collision and episodic persistence.

## Explicit trust boundary

This is **not** an LLM prompt-injection proof or an authorization source.
Stored `origin` and `tags` are not cryptographically authenticated.
Simple text indicators catch only known patterns; a novel untagged instruction
can still be stored, retrieved and interpreted by an LLM. Older semantic
memories are not automatically reclassified. This checkpoint does not alter
`PolicyCapabilities` or the independent approval requirement for destructive
operations.

The rollout stays in local staging until end-to-end tests prove that action
plans cannot use memory records or retrieved workspace files to expand
capabilities. Disallowing semantic promotion does not delete a record;
ordinary memory pressure eviction and user-controlled retention remain
separate behaviors.

## Acceptance / measurements

- TDD RED reproduced missing gate and cross-source key-collision defects
  (failing test cases prior to corrections).
- Focused tests: **33/33 passed** in the final focused run.
- Comprehensive Atlas pytest suite after final edits: **1285 passed, 3 skipped, 196 subtests passed** in 31.27 seconds (x99, exit 0).
- This is local test evidence, not a live Pentium / Hermes / Discord certification.
- Static check: `git diff --check` restricted to touched tracked files.
- No model/provider changed, no API payments, no servers restarted, no
  production migration, no commit/deploy.

## Follow-up security and benchmark gates

1. **CP-MEM-P1:** provenance signed by a trusted ingress, immutable type
   classification, content-addressed evidence and separate operator-approved
   instructions. Reject tampering across files and DB rows.
2. **CP-MEM-P2:** enforce coherence at the action-authorization sink (not
   merely at retrieval/prompt), with a traceable correlation ID, risk scoring,
   review/quarantine and human approvals for high-impact actions.
3. **CP-MEM-P3:** adversarial longitudinal sessions and 30%-injected poisoning
   corpus. Measure false approvals, false blocks, repeat contamination,
   classification drift, decision trace completeness, and tokens. Include
   existing semantic data and agent-written filesystem artifacts.
4. Canary only with real Pentium backup, release gate, rollback rehearsal and
   independent review; rollback by restoring prior files plus controlled
   migration if a persistent schema is introduced later.
