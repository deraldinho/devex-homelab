# Atlas CP-H11/CP-H12 — Certification Evidence (2026-10-10)

## Outcome
**LOCAL GREEN / PHYSICAL PENDING**. Do not promote self-healing or mark CP-H12 globally green.

## Verified x99 repository
- Root: `C:\Users\deral\DevEx-HomeLab`
- Branch: `atlas/v0.4.0-proprioception-autonomy`, 14 local commits ahead of origin at entry; observed HEAD `2a62765`.
- Relevant configs: `infrastructure/pentium/agent/config.json` and `infrastructure/pentium/atlas/config_health_supervisor.json`.
- `health_supervisor_v1: true`, `self_healing_v1: false`.
- Managed `core` and `x99` hosts have empty `allowed_controls`, `allowed_services`; no automatic recovery targets approved.
- TCP reachability and HTTP `/healthz` from x99 were observed in previous CP-H11 read-only inventory, but **do not prove functional health of all Pentium processes**.

## Local tests and verification
- `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests infrastructure/pentium/agent/tests -q` → **1018 passed, 3 skipped, 42 subtests passed**, 31.15s (before adding rollout guard).
- Added `infrastructure/pentium/atlas/tests/test_self_healing_rollout_guard.py`:
  - unverified managed targets remain read-only;
  - self-healing feature flag remains disabled before inventory certification.
- `py -m pytest --import-mode=importlib infrastructure/pentium/atlas/tests/test_self_healing_rollout_guard.py -q` → **2 passed**.
- Duplicate `test_cli.py` import collision in the original combined pytest invocation is avoided by `--import-mode=importlib`.
- Tests for rejected policy, stale preconditions, failed postcondition, cooldown and attempt budgets exist in `test_recovery_controller.py`; they rely on test doubles and are not proof of a physical recovery.
- No new automatic privileges and no live service restarts performed.

## Blocker and truthful limitations
- Remote Desktop Commander currently connects to **x99** only; no direct Pentium agent connection is present.
- Automated SSH from the connected remote tool ends with code 1 and no usable remote output, although the user's manual SSH works and port 22 is reachable.
- Consequently: live supervisor snapshot, functional discord session, process PIDs, actual core inventory, rollout release and verified reversible fault injection have **not** been independently checked.
- Never claim physical success based on local unit tests or basic HTTP 200.

## Safe completion sequence
1. Establish authenticated, non-interactive SSH into Pentium using a pre-authorized key/transport, without disabling host verification or copying secrets into logs.
2. Read-only snapshot of `systemctl --user` services, runtime health snapshot and effective flags. Record evidence/timestamps/PIDs.
3. Enumerate actual core/x99 services via existing managed-read transport; require explicit approval before adding exact reversible control targets.
4. Prove denial of destructive control in a dry-run fixture. Fault-test disposable service only after authorization and backup/rollback.
5. Confirm independent functional postcondition and no restart loop. Run full suite again after changes.
6. Only then consider enabling self-healing for verified narrow targets. Keep voice intentionally paused.

## Rollout decision
**HOLD** — no deploy, no switch of `self_healing_v1`, no remote restart, no widened allowlist. Preserve current live installation and all local commits.
