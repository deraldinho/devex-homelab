# Atlas — CP-MEM-P1: signed ingress provenance and immutable typing

**Date:** 2026-10-16
**Predecessor:** CP-MEM-P0 (`docs/implementation/2026-10-16-atlas-p0-memory-coherence-gate.md`)
**State:** implemented and tested locally on x99; Pentium deployment **HOLD**.

## Verified baseline / rationale

Canonical checkout: `C:\Users\deral\DevEx-HomeLab` on branch
`atlas/v0.4.0-proprioception-autonomy`. The tree already contained unrelated
modified/untracked files; none were reset, staged, committed, deployed or
restarted. `py -m pytest` on the memory suites was GREEN (32 passed) before any
edit.

CP-MEM-P0 classified memories by *tag claims* and treated `content`/`origin`
as unauthenticated text. A modified database row or a re-written tag could
therefore change what a record asserted, with no integrity signal. P1 adds a
trust boundary at ingestion: a trusted ingress signs a content-addressed
attestation that fixes the memory's immutable `kind` and identity.

## Scope implemented

1. `memory_ingress.py` (new, stdlib only):
   - `TrustedKeyRegistry`: runtime-only shared secrets (HMAC-SHA256); keys are
     never read from or written to the repository; constant-time verification;
     unknown principals are never trusted.
   - `MemoryIngress.attest(...)`: assigns the immutable `kind` at ingress and
     signs a canonical payload binding `memory_id`, `content`, `origin`,
     `entity_id`, `created_at` and `kind` through a SHA-256 content address.
   - `MemoryIngress.verify(...)`: returns an `IngressVerdict`; rejects unknown
     ingress, forged signature, subject mismatch and content-address mismatch.
   - `OperatorAuthority` + `OperatorInstruction`: operator-approved
     instructions require an independently signed approval and live in their
     own table. `OperatorAuthority.persist()` verifies the signature **before**
     storage.
   - `MemoryKind` moved here (lower layer) and re-exported by the gate.
2. `memory_coherence_gate.py`: `review_promotion(record, *, verdict=None)`.
   With a verified `verdict`, the attested `kind` is authoritative and a
   conflicting tag claim is rejected (`kind_conflict`); without a verdict the
   P0 tag-derived path is unchanged. New `declared_kind()` helper. `PromotionReview`
   gained `kind_source` and `attested`.
3. `memory_store.py`: additive tables `memory_attestations` (keyed by
   `subject_id`) and `operator_instructions`. `save_attestation` /
   `get_attestation` (a corrupt row is treated as absent, never trusted),
   `save_operator_instruction` / `get_operator_instruction` /
   `list_operator_instructions`. Exact replay is idempotent; conflicting replay
   raises. `delete`/`consolidate` remove orphan attestations. Schema stays
   readable at v1/v2/v3 (additive columns/tables only).
4. `memory_manager.py`: optional `ingress`; `remember(..., attestation=...)`
   persists the record and its attestation; `_promote_recurrent` evaluates each
   candidate against its stored attestation verdict.
5. `memory_retriever.py`: optional `ingress`; attested records report
   `authority=evidence_only` plus `integrity` (`attested`/`tampered`) and the
   immutable `memory_kind`. Operator instructions never appear here.
6. `foundation-ci.yml`: `memory_ingress.py` and `memory_coherence_gate.py` added
   to the `py_compile` gate.

## Explicit trust boundary

- The content address (SHA-256) is a **corruption** check only; the HMAC
  signature is the sole authentication element. A party with the DB write
  privilege but without the ingress key cannot forge a valid attestation, but
  can *delete* an attestation row — the record then falls back to the stricter
  P0 evidence-only path, never to elevated trust.
- `layer`, `frequency`, `importance`, `confidence`, protection flags and tags
  are intentionally outside the address (they evolve legitimately). Repeated
  recurrence still cannot inflate confidence/importance/criticality.
- Simple text indicators remain defence in depth; a novel untagged instruction
  can still be stored and retrieved **as untrusted evidence**. No action
  authorization is derived here.
- Production key provisioning, key ACLs and rotation are a separate operational
  gate. No secret is created by this checkpoint.

## TDD / Quality Gates

- RED reproduced: with `memory_ingress.py` absent the P1 module failed to
  import; with the contract present but integrations missing, **12 of 22** P1
  tests failed (store/manager/retriever/gate-wiring absent).
- GREEN: `test_memory_ingress.py` **22/22 passed**.
- Focused memory suites (P0 + P1 + store + manager + retriever + model): **52 passed**.
- Full Atlas suite `infrastructure/pentium/atlas/tests`: **1415 passed, 8 skipped,
  217 subtests passed** (x99, exit 0).
- `py -m py_compile` on the five touched modules: exit 0. `git diff --check`: exit 0.
- Static: no `TODO`/`TBD` markers introduced (Foundation CI guard).

## Files touched in this checkpoint

- `infrastructure/pentium/atlas/memory_ingress.py` (new)
- `infrastructure/pentium/atlas/memory_coherence_gate.py`
- `infrastructure/pentium/atlas/memory_store.py`
- `infrastructure/pentium/atlas/memory_manager.py`
- `infrastructure/pentium/atlas/memory_retriever.py`
- `infrastructure/pentium/atlas/tests/test_memory_ingress.py` (new)
- `.github/workflows/foundation-ci.yml`
- `docs/implementation/2026-10-16-atlas-mem-p1-signed-ingress.md` (new)

## Blockers for production and next gates

- No live ingestion path composes `MemoryIngress`/`OperatorAuthority`; key
  provisioning and the real ingestion boundary must be wired and E2E-proven in
  QA before deploy. Nothing is activated by this checkpoint.
- Existing persisted memories are not retro-attested; a controlled re-attest or
  migration plan is required, preserving rollback.
- **CP-MEM-P2:** enforce coherence at the action-authorization sink (not merely
  retrieval/prompt), with a traceable correlation ID, risk scoring,
  review/quarantine and human approvals for high-impact actions.
- **CP-MEM-P3:** adversarial longitudinal sessions and a poisoning corpus;
  measure false approvals/blocks, contamination, classification drift and token
  cost, including existing semantic data and agent-written files.
- Canary only with real Pentium backup, release gate, rollback rehearsal and
  independent review.
