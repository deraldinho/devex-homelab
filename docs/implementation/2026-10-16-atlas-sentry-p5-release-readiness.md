# Atlas — SENTRY-P5: release readiness, trusted ownership and staged bundle

Date: **2026-10-16**. Production status: **HOLD (not deployed)**.

## Aim

Close the safety and operability prerequisites discovered after CP-SENTRY-P4
without confusing a green unit test with an authorized production activation.

- `tools/atlas_sentry_p5_preflight.py`: read-only Linux gate. No sudo,
  service changes, SSH, secret reads, or activation. Output is structured
  JSON with independent named checks. Exit 2 when the environment is not
  ready; exit 0 only when the *prerequisites* pass, but
  **production_ready and release_authorized always remain false** until
  the independent real-principal canary and operator approval are recorded.
- `tools/atlas_sentry_p5_bundle.py`: deterministic secret-free ZIP containing
  **17 specifically allowlisted source/config/service files**. Verifies
  filename allowlist, no duplicate entries, bounded sizes, SHA-256 for each
  member, and whole-bundle SHA-256. Rejects symlinks, unexpected files,
  tampering, traversal, missing sources and existing output overwrite.
  SHA-256 is a corruption check, **not a signature or authentication of
  publisher**. The Git commit and operator-reviewed release artifact must
  supply release provenance.
- `tools/test_atlas_sentry_p5_preflight.py` and
  `tools/test_atlas_sentry_p5_bundle.py`: adversarial tests; include
  false systemd comment spoof, executor-writable trusted code, missing
  principals/group, crypto unavailable, missing units, stale/unsafe health
  config, archive tampering and forced release misclassification.
- `infrastructure/pentium/atlas/systemd-system/atlas-sentry-health.service`:
  opt-in template for a **dedicated health Unix account** with a root-owned
  trusted code tree, unprivileged mode, empty Linux capabilities and
  constrained write targets. Template is NOT installed or activated.

## Threat boundary

**Two Unix UIDs are necessary but not sufficient.** The independent
health principal must load code, config, systemd units and public trust
policy from root-owned, non-group/world-writable paths, with no symlink
component. An executor-controlled code path nullifies the cryptographic
separation. The preflight validates ownership/perms all the way to the
filesystem root for required trusted health files and the two system
unit files.

The relay must run as the trusted health principal, accepting only
`SO_PEERCRED`-authenticated requests from the cognitive executor UID.
An executor never gets the health private key, the health SQLite write
privilege, or journal write privilege.

The shipped `SystemdUserProbe` checks the calling user's `systemctl
--user`. Under the proposed independent system account it **does not
automatically observe deraldinho's user-session services**. Before the
service can sign real HEALTHY attestations, the independent health
principal must be validated against actual process and functional
probes. Failing probes must not be bypassed with static HEALTHY states.

## Verified Pentium facts (read-only SSH)

- The user-session `atlas-cognitive.service` is active.
- The `atlas-health-supervisor.service` unit is **not installed** in
  that session; it is inactive.
- Deployment path `~/pentium-agent/atlas/` exists, but the deployed
  health configuration and the Sentry P0–P4 modules are missing.
- The dedicated `atlas-sentry-health` system account and shared
  `atlas-sentry-relay` group are missing.
- `sudo -n` is unavailable, so provisioning separate system identities
  or installing root-owned system units cannot be completed under the
  current unattended privilege boundary.
- Python 3.14.4 and cryptography 46.0.5 are present, and the existing
  cognitive service remains active.
- Running the P5 preflight against **actual installed paths** returned
  `production_ready=false` and per-check missing prerequisite reasons.
- `systemd-analyze verify` accepted the proposed health and relay
  system unit templates in a non-installed staging directory. Existing
  unrelated host warnings from XFS units were present.
- The 17-file stage ZIP was copied to a private `/tmp` directory on
  the Pentium and verified to have the exact same bundle SHA-256 as
  the x99 build. Final staging artifact SHA-256:
  `d1211a2e0f664b592e9753a1d564757e8f477f8d8d754cf6fe803a14f1906b03`.
  **Nothing was installed or restarted.**
- The final Pentium preflight explicitly rejected executor-writable
  health code, absent service identities and group, missing deployed
  modules/config and absent system units/services. It returned
  `preflight_passed=false`, `production_ready=false`,
  `release_authorized=false`.

## Test evidence

- Windows x99 local P5 tests: **20 run, 19 passed, 1 skipped**.
- Full Atlas regression plus P5 suite (last run): **1412 passed,
  9 skipped, 217 subtests passed**, exit code 0.
- Pentium systemd-analyze verify: unit templates accepted
  (only unrelated legacy XFS warnings).
- Pentium ZIP verification: 17/17 allowed files, exact SHA-256 match.

## Recovery/rollback policy

1. Keep `ATLAS_SENTRY_V2_*_ENABLED` and
   `ATLAS_SENTRY_HEALTH_SHADOW` off in production until all independent
   observations pass. Do not auto-enable from this plan.
2. First provision dedicated principals, trusted root-owned code,
   externalized private keys, root-owned public trust bundle, and
   appropriately mounted *read-only* target health evidence.
3. Run the read-only P5 gate and inspect every failed check. A green
   preflight is **not** sufficient release authority; execute a
   nondestructive authenticated cross-UID canary next.
4. Take a verified backup of installed files, SQLite state, all
   systemd units and environment *without copying private keys into
   Git or logs* before applying changes.
5. In case of failure, turn off Sentry feature flags and stop only the
   newly installed P5 system services; keep healthy pre-existing
   cognitive services untouched and preserve signed journals for audit.

## Reproducible commands

From x99:

```powershell
py -m unittest tools.test_atlas_sentry_p5_preflight tools.test_atlas_sentry_p5_bundle -q
py -m tools.atlas_sentry_p5_bundle --build C:\\path\\to\\new-stage.zip
py -m tools.atlas_sentry_p5_bundle --verify C:\\path\\to\\new-stage.zip
```

On Pentium, without sudo or mutation:

```sh
python3 /tmp/atlas-sentry-p5-preflight.py \\
  --deploy-root /home/deraldinho/pentium-agent \\
  --trusted-health-root /opt/DevEx-HomeLab/infrastructure/pentium \\
  --user-unit-dir /home/deraldinho/.config/systemd/user \\
  --system-unit-path /etc/systemd/system/atlas-sentry-receipt-relay.service \\
  --system-health-unit-path /etc/systemd/system/atlas-sentry-health.service
```

Remaining **BLOCKERS**: authorized root provisioning, trusted code owner
and key ACLs, functional probe visibility from separate health account,
cross-principal nondestructive signed canary, and staged rollback proof.

**No push, installation, secret creation, live deploy, or live service
restart was performed in this checkpoint.**
