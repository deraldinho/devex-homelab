# CP21 — Atlas multi-agent orchestration (2026-10-15)

Status: STAGING / IN PROGRESS; PRODUCTION BLOCKED.

## Evidence observed
- x99 Desktop Commander online; OpenCode main server 127.0.0.1:49374.
- Three repository-bound fork sessions created from previous Atlas reviews; original sessions unchanged.
- Implementation candidate: ses_ebfc7907cffe51Rj3MaoOPqCYS; message msg_14038c431001VMowJJblPtDcJM.
- Security review: ses_ebfc71b92ffex1VObLwyoJxHER; message msg_140391bc0001OH7GQyamiD3dHB.
- QA review: ses_ebfc70be8ffe37PG1skPlnFCVu; message msg_1403929f9001d21zalWuaIusDE.
- Main OpenCode API accepted messages; fork implementation inherits plan-mode metadata. BUILD execution is NOT verified. This is a blocker, not success.
- Python full staging suite: 348 tests run, 3 skipped, zero failures. git diff --check passed.

## P0 blockers
1. Create truly build-enabled, repository-scoped execution sessions. Prove execution by resulting diff, tool activity, terminal result and test receipt. Never infer success merely from message accepted.
2. Bind host-enforced sandbox permissions and signed session receipts; reconcile pending/failed sessions, ensure retries do not duplicate work.
3. Wire CP20 fail-closed evidence gate into native operational workflow; independent security review and negative tests mandatory.
4. Verify provenance/NTP/HMAC custody, Discord ACK, rollback, Windows and Linux safety preflight.

## P1/P2
- Cognitive input -> context -> LLM -> natural Discord response, monitoring and approval-gated remediation.
- Graph-based persistence and metric events for synthetic emotional state; failover and crash recovery.
- End-to-end x99/core/pentium staging and production approval gates.

## Release policy
No automatic deployment, credential export, destructive remediation or production promotion until real host evidence and independent Quality Gates. Existing dirty changes must be preserved; do not reset or overwrite them.
