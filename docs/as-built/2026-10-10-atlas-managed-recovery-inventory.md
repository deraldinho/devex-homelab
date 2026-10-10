# Atlas — CP-H11 Managed Recovery Inventory (2026-10-10)

## Scope
Read-only inventory on x99 via Remote Desktop Commander. The installed Pentium managed inventory was **not** queried, because automated SSH execution from the tool did not return a usable authenticated session. No change to allowed controls was made.

## Repository baseline
- Branch: `atlas/v0.4.0-proprioception-autonomy`; HEAD observed `2a62765`; 14 commits ahead of origin.
- `infrastructure/pentium/agent/config.json`: `core` and `x99` enrolled as MANAGED, but `allowed_controls: []` and `allowed_services: []` for **both**.
- `infrastructure/pentium/atlas/config_health_supervisor.json`: `health_supervisor_v1: true`, `self_healing_v1: false`.
- Existing inventory remains least-privilege READ-only. Do not authorize wildcard target or inferred service controls.

## Direct physical evidence from x99
Read-only commands via Remote Desktop Commander on x99:
- `hostname` → `x99`.
- TCP probe `192.168.88.3:22` → reachable (`True`).
- HTTP `http://192.168.88.3:8765/healthz` → `{"status":"ok"}`; proves only health endpoint response, **not** supervisor functional health of all components.
- Windows services observed: `com.docker.service` Running, `ssh-agent` Running, `sshd` Running, `SshdBroker` Stopped, `Tailscale` Running. No restart authorized from this observation.
- Automated SSH `deraldinho@pentium` failed to yield a usable remote shell in earlier attempts; latest batch stderr/stdout were empty. Manual user SSH works, but the tool's non-interactive access was not verified. Do not assume deployment access.
- Core runtime state and service/container inventory: **not verified**.

## Policy decision
**Do not promote auto CONTROL** for core or x99 in this checkpoint. Evidence is not sufficient to approve exact reversible service/container targets, especially on core. Preserve empty allowlists and keep `self_healing_v1` disabled.

## Verification
- `py -m pytest --import-mode=importlib infrastructure/pentium/agent/tests/test_managed_inventory.py infrastructure/pentium/agent/tests/test_cli.py infrastructure/pentium/atlas/tests/test_health_supervisor_daemon.py infrastructure/pentium/atlas/tests/test_recovery_controller.py -q` → 22 passed.
- Earlier full Atlas+agent local suite: 1018 passed, 3 skipped, 42 subtests passed; importlib isolation required because both suites contain `test_cli.py`.
- No production code or operational configuration modified.

## Remaining acceptance gates
1. Independently authenticate to Pentium via bounded existing managed transport, observe `systemctl --user`, canonical snapshot, logs and effective deployed release.
2. Confirm core/x99 targets through read-only managed inventory and obtain explicit risk approval for any narrowly allowlisted reversible controls.
3. Run controlled fault smoke only on disposable/approved target, verify functional postcondition and no repeated recovery.
4. Record pre/post service PIDs, health states, authorization denial for destructive `reboot_host`, evidence refs, rollback and timestamps.
5. Then, and only then, consider `self_healing_v1` rollout.

Status: **CP-H11 read-only inventory partially verified; control promotion blocked intentionally; CP-H12 physical certification pending.**
