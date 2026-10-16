# CP-NATIVE-DISPATCH — 2026-10-15
Status: STAGING_GREEN / REVIEW_OUTBOX_ONLY / PRODUCTION_BLOCKED.

## Implemented
- atlas_native_dispatch.py: transactional SQLite read-only agent review requests; fixed role allowlist, deterministic task ID, at-most-one outbox record per mission and role, fingerprint recheck, fail-closed drift handling.
- test_atlas_native_dispatch.py: four tests for idempotence, authorization boundary, role allowlist, and drift.
- Integrates with atlas_native_workflow.py from the prior staging checkpoint. No LangGraph dependencies.

## Tests
python -m unittest discover -s . -p test_*.py -q
306 tests, OK, 3 skipped (Windows symlink limitation).
git diff --check OK.

## Security limitation
A PENDING outbox entry is a proposal, NOT an OpenCode process launch, authenticated agent execution, or deployment authorization. Consumers must independently validate signed policy receipts, frozen snapshots, filesystem/OS isolation, cost budget and idempotency. No production services touched. Independent reviewer, Linux NTP tests, rollback and Discord ACK remain blocking.
