# Atlas native integration 2026-10-15

Status: STAGING_TESTED / PRODUCTION_BLOCKED

## Implementation
- atlas_native_free_runner.py: injectable interface to existing OpenCode FreeModelFailover, requires external sandbox attestation, baseline SHA256, read-only policy; tested with fake manager.
- test_atlas_native_free_runner.py: rejects missing attestation and baseline drift, confirms injected runner contract.
- atlas_native_readiness.py: nine mandatory evidence categories and unconditional production hold pending independent verification.
- test_atlas_native_readiness.py: three production-hold regression tests.
- Prior native mission engine, SQLite outbox, single-claim executor, model adapter, clock/SQLite hardening preserved; no LangGraph.

## Evidence
OpenCode local /api/info HTTP 200, version 2.0.29. This is reachability, NOT completed agent execution.
Windows full suite: 319 tests OK, 3 skipped.
No real OpenCode mission launched and no live Linux/Pentium attestation.
All modifications remain in isolated CP-ATLAS-RECON-20261015 staging clone.
No deploy, no production restart, no promotion to baseline CP16.

## Safety blockers
OS sandbox attestation cannot be created by a plain Python dict or prompt alone; requires out-of-process verifier.
Authenticated signed receipt owner, NTP, HMAC custody, Discord ACK, DR/rollback, Linux TOCTOU, independent review and explicit production approval are outstanding.
Automatic retries of ambiguous provider sessions stay blocked.
