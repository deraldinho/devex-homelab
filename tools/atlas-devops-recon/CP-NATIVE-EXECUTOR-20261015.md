# CP-NATIVE-EXECUTOR — 2026-10-15
Status: STAGING_GREEN / NO LIVE RUN / PRODUCTION_BLOCKED

## Implemented
- atlas_native_executor.py: single-claim SQLite ledger, crash-safe IN_FLIGHT state, no automatic replay, idempotent terminal receipts and conflict protection.
- atlas_native_opencode_adapter.py: injected runner boundary for the existing free-only OpenCode manager, read-only review, strict zero-cost receipt and bounded report.
- test_atlas_native_executor.py and test_atlas_native_opencode_adapter.py: 8 unit regression tests.
- Previous CP18/CP19/natural workflow preserved. LangGraph not used.

## Validation
Command: python -m unittest discover -s . -p test_*.py -q
Result: 314 tests, OK (3 skipped due to Windows symlink support).
git diff --check: exit 0.

## Unresolved high-risk integration gates
This is NOT an OS-sandboxed agent runtime. It has not launched a real OpenCode session.
External caller may invoke finish: authenticated/authorized receipt writer must be implemented before deployment.
Need authoritative session IDs, durable reconcile with signed provider results, no ambiguous replay, host cross-clock attestation, real HMAC custody, external notification ACK, sandbox rollback, Linux TOCTOU tests, independent QA, and production approval.
PENDING and IN_FLIGHT are not proof of successful agent work.
