# CP19 — SQLite URI hardening (2026-10-15)

Status: STAGING_GREEN / PRODUCTION_BLOCKED.

## Baseline
Isolated clone from CP16 (237b524). CP16 original unchanged.

## Implementation
- sqlite_uri_safety.py: canonical percent encoding of resolved paths, mode=ro, optional immutable=1, fail closed on absent and direct symlink paths.
- system_supervision.py: switched read-only ledger URI construction to shared utility.
- autonomy_policy_gate.py: switched read-only inbox URI construction to shared utility.
- test_sqlite_uri_safety_cp19.py: tests reserved filename chars, read-only SQL, absent files and symlink rejection.

## Verification
Command: python -m unittest discover -s . -p test_*.py -q
Result: 297 tests OK, 3 skips on Windows x99.
git diff --check: OK.

## Residual blockers
The URI helper is not OS-level openat/O_NOFOLLOW containment: parent-directory symlink TOCTOU must still be assessed.
Independent security review, Linux and Windows symlink tests, live NTP attestation, HMAC key custody, external notification ACK, rollback and cognitive bridge remain unresolved.
No service restart, no promotion, no production deployment.
