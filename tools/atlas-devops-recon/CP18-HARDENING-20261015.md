# CP18 — Clock hardening staging (2026-10-15)

Status: STAGING_GREEN; PRODUCTION_BLOCKED.

## Baseline
Local clone of CP-ORCH-16/release_candidate at commit 237b524.
Original CP16 working tree was not modified.

## Changes
- trusted_cross_host_clock.py: bounded and finite RTT/uncertainty (<=300s); bounded sample age and TTL (<=86400s); fail closed for explicit provenance.verified conflict; reject host observations outside +/-300s from assessment instant.
- test_clock_hardening_cp18.py: 9 additional tests including adverse bounds, contradictory provenance, stale/future host observations and valid reference.

## Verification
- Red phase: 8 of 9 new regressions initially failed.
- Green phase: python -m unittest discover -s . -p test_*.py -q
- Result: Ran 294 tests; OK (skipped=2), Windows x99. Skips belong to existing OS symlink coverage.
- Review of operational NTP attestation, HMAC custody, Discord ACK and rollback remains pending.

## Gates
- Staging candidate only. No live deployment, no production authorization.
- Do not promote without Linux test matrix, independent code audit and external attestation.
- This checkpoint only addresses bounded sample validation; it is not a full CP17/18/19 sign-off.
