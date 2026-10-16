# CP outbox lifecycle — 2026-10-15

User approved hierarchical delegation checkpoint. Prior QA/architecture reports recovered and inspected.

## TDD
Two RED regressions confirmed list_pending incorrectly returned already claimed and already succeeded tasks.
Updated atlas_native_dispatch.list_pending: LEFT JOIN execution_receipts when ledger table exists, excluding tasks with any receipt, even IN_FLIGHT. Falls back safely to pending outbox only when ledger table absent.
test_atlas_native_outbox_lifecycle.py: claimed and succeeded cases.
Verification: 342 tests OK (3 Windows symlink skips); git diff --check exit 0.
No deployment or production change.

## Agent and model policy
Current OpenCode API 2.0.29 healthy. /api/provider returned no match for free/Nemotron/Ultra model keys through catalog inspection; exact Nemotron 3 Ultra A550B model identifier and zero-price availability NOT established from this query. Retain bounded allowlist of previously known free model IDs; no paid automatic fallback.
Hierarchical delegation module is tested but does not itself spawn live agents. Host-enforced tool permissions, OpenCode lifecycle adapter, signed receipts, Linux tests, NTP, Discord ACK and independent QA remain outstanding.
