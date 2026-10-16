# CP-NATIVE-WORKFLOW (2026-10-15)

Decision: Atlas native engine; no LangGraph runtime dependency.

## Changes in isolated CP16 staging clone
- atlas_native_workflow.py: deterministic review state machine persisted in SQLite WAL, unique mission ID, baseline SHA-256, idempotent replays, drift/collision denial, explicit boolean approval, read-only status. No permissions to execute or deploy.
- test_atlas_native_workflow.py: five tests for restart, idempotence, denial, missing baseline, ID collision and approval type.
- Removed experimental LangGraph files and isolated venv. No production service touched.
- Prior CP18/CP19 staging fixes preserved.

## Verification
python -m unittest test_atlas_native_workflow -q: 5 OK.
python -m unittest discover -s . -p test_*.py -q: 302 OK, 3 skipped (Windows symlink).
git diff --check: OK.

## NOT YET IMPLEMENTED
OpenCode dispatch integration, agent resource isolation, typed policy receipt validation, durable signed event transport to Pentium, Discord delivery ACK, sandbox rollback, real NTP attestation, and Linux independent QA.
Review approval is not execution authorization; production remains blocked.
