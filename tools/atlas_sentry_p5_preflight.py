"""CP-SENTRY-P5: read-only, fail-closed Pentium production readiness gate.

No deploy, sudo, process restart, secret access or state mutation. A successful
result means prerequisites are visible to the verifier; it is not evidence
that a release was deployed or a recovery worked in production.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import stat
try:
    import pwd
    import grp
except ImportError:  # Windows development; the production gate is Linux-only.
    pwd = grp = None
import subprocess
from dataclasses import dataclass
from pathlib import Path

MANDATORY_CONFIG = (
    "config_health_supervisor.json",
    "health_supervisor_daemon.py",
    "failure_memory.py",
    "sentry_receipt_v2.py",
    "sentry_receipt_relay.py",
    "sentry_incident_manifest.py",
)
USER_SERVICE = "atlas-cognitive.service"
SYSTEM_HEALTH = "atlas-sentry-health.service"
SYSTEM_RELAY = "atlas-sentry-receipt-relay.service"


@dataclass(frozen=True)
class Result:
    check: str
    ok: bool
    reason: str


def _result(check, ok, reason="ok"):
    return Result(check, bool(ok), reason if not ok else "ok")


def _run(argv):
    try:
        outcome = subprocess.run(argv, text=True, capture_output=True,
                                 timeout=5, check=False)
        return outcome.returncode == 0, outcome.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False, ""


def _safe_file(path, *, owner=None, mode=None):
    # No symlinks including final node; fail closed on files not owned by role.
    if not path.is_absolute() or path.is_symlink():
        return False
    try:
        info = path.stat()
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode):
        return False
    if owner is not None and info.st_uid != owner:
        return False
    if mode is not None and info.st_mode & 0o777 != mode:
        return False
    return True


def _immutable_root_tree(path):
    """Fail closed if a trusted module or any ancestor is owner-writable by
    the executor. The trusted health service must load root-owned code only.
    """
    try:
        if not path.is_absolute():
            return False
        lexical=path
        while True:
            if lexical.is_symlink():
                return False
            if lexical.parent==lexical:
                break
            lexical=lexical.parent
        resolved=path.resolve(strict=True)
        if not resolved.is_file():
            return False
        current=resolved
        while True:
            info=current.stat()
            if info.st_uid!=0 or info.st_mode & 0o022:
                return False
            if current.parent==current:
                return True
            current=current.parent
    except (OSError,RuntimeError):
        return False


def audit(*, deploy_root, trusted_health_root, user_unit_dir, system_unit_path,
          system_health_unit_path, health_user="atlas-sentry-health",
          relay_group="atlas-sentry-relay",
          executor_user="deraldinho", allow_inactive=False):
    if os.name != "posix":
        return [_result("linux_runtime", False, "linux_required")]
    root = Path(deploy_root)
    unit_dir = Path(user_unit_dir)
    system_unit = Path(system_unit_path)
    health_unit = Path(system_health_unit_path)
    findings = [
        _result("deployment_root", root.is_dir() and not root.is_symlink(),
                "deployment_root_missing"),
    ]
    atlas = root / "atlas"
    trusted=Path(trusted_health_root)
    findings.append(_result(
        "independent_health_code_immutable",
        all(_immutable_root_tree(trusted/"atlas"/name)
            for name in MANDATORY_CONFIG),
        "independent_health_code_must_be_root_owned_and_nonwritable",
    ))
    for name in MANDATORY_CONFIG:
        findings.append(_result(
            "package_" + name.replace(".", "_"),
            _safe_file(atlas / name), "required_deployed_file_missing"))
    config_path = atlas / MANDATORY_CONFIG[0]
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        healthy_config = (
            type(config) is dict
            and config.get("schema_version") == 1
            and isinstance(config.get("components"), dict)
            and len(config["components"]) >= 1
            and config.get("features", {}).get("health_supervisor_v1") is True
            and config.get("features", {}).get("self_healing_v1") is False
        )
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
        healthy_config = False
    findings.append(_result("supervisor_config",
                            healthy_config,"supervisor_config_missing_or_unsafe"))
    findings.append(_result(
        "cognitive_user_unit", _safe_file(unit_dir / USER_SERVICE),
        "cognitive_user_unit_missing"))
    def _role_unit(path, exec_module):
        if not _safe_file(path):
            return False
        # systemd intentionally allows repeated Environment=/ExecStart= keys.
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        try:
            with path.open(encoding="utf-8") as stream:
                parser.read_file(stream)
            service = parser["Service"]
        except (OSError,UnicodeError,KeyError,configparser.Error):
            return False
        return (
            service.get("User") == health_user
            and service.get("Group") == health_user
            and service.get("NoNewPrivileges") == "true"
            and service.get("ProtectSystem") == "strict"
            and service.get("CapabilityBoundingSet") == ""
            and service.get("AmbientCapabilities") == ""
            and "AF_UNIX" in service.get("RestrictAddressFamilies", "").split()
            and exec_module in service.get("ExecStart", "")
            and _immutable_root_tree(path)
            and (
                exec_module != "atlas.health_supervisor_daemon"
                or service.get("WorkingDirectory") == str(trusted)
            )
        )
    findings.append(_result(
        "relay_system_unit",
        _role_unit(system_unit,"tools.atlas_sentry_v2_relay"),
        "relay_system_unit_missing_or_unsafe"))
    findings.append(_result(
        "independent_health_system_unit",
        _role_unit(health_unit,"atlas.health_supervisor_daemon"),
        "independent_health_unit_missing_or_unsafe"))
    try:
        executor = pwd.getpwnam(executor_user)
        health = pwd.getpwnam(health_user)
        identities = executor.pw_uid != health.pw_uid and health.pw_uid != 0
    except KeyError:
        executor = health = None
        identities = False
    findings.append(_result("separate_unprivileged_uids",
                            identities, "distinct_service_accounts_required"))
    try:
        group = grp.getgrnam(relay_group)
        # An installed shared socket group is necessary but not sufficient.
        group_ok = bool(identities and group.gr_gid != 0)
        if group_ok:
            executor_groups = os.getgrouplist(executor_user, executor.pw_gid)
            health_groups = os.getgrouplist(health_user, health.pw_gid)
            group_ok = group.gr_gid in executor_groups and group.gr_gid in health_groups
    except (KeyError, OSError, AttributeError):
        group_ok = False
    findings.append(_result("socket_group_membership",group_ok,
                            "dedicated_shared_socket_group_required"))
    exists, _ = _run(("python3", "-c",
                       "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey"))
    findings.append(_result("ed25519_runtime", exists,
                            "cryptography_ed25519_dependency_missing"))
    active, _ = _run(("systemctl","--user","is-active",USER_SERVICE))
    findings.append(_result("cognitive_service_active", active,
                            "cognitive_runtime_inactive"))
    health_active, _ = _run(("systemctl","is-active",SYSTEM_HEALTH))
    findings.append(_result("independent_health_active",health_active or allow_inactive,
                            "independent_health_service_inactive"))
    relay_active, _ = _run(("systemctl","is-active",SYSTEM_RELAY))
    findings.append(_result("relay_system_service_active",relay_active or allow_inactive,
                            "relay_system_service_inactive"))
    # P5 deliberately does NOT read secret files, scan env values or assume
    # the activated units are running the intended version.
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only Atlas Sentry P5 release gate")
    parser.add_argument("--deploy-root",required=True,type=Path)
    parser.add_argument("--trusted-health-root",type=Path,
                        default=Path("/opt/DevEx-HomeLab/infrastructure/pentium"))
    parser.add_argument("--user-unit-dir",required=True,type=Path)
    parser.add_argument("--system-unit-path",required=True,type=Path)
    parser.add_argument("--system-health-unit-path",required=True,type=Path)
    parser.add_argument("--health-user",default="atlas-sentry-health")
    parser.add_argument("--executor-user",default="deraldinho")
    parser.add_argument("--relay-group",default="atlas-sentry-relay")
    parser.add_argument("--allow-inactive",action="store_true",
                        help="Audit staging only; never counts as production readiness")
    args = parser.parse_args(argv)
    checks = audit(
        deploy_root=args.deploy_root,
        trusted_health_root=args.trusted_health_root,
        user_unit_dir=args.user_unit_dir,
        system_unit_path=args.system_unit_path,
        system_health_unit_path=args.system_health_unit_path,
        health_user=args.health_user,
        executor_user=args.executor_user,
        relay_group=args.relay_group,
        allow_inactive=args.allow_inactive,
    )
    ok = all(item.ok for item in checks) and not args.allow_inactive
    print(json.dumps({
        "schema_version":1,"checkpoint":"SENTRY-P5",
        "preflight_passed":ok,
        # The preflight does not inspect secrets or certify an independent
        # cross-principal canary; it NEVER grants deployment authority.
        "production_ready":False,
        "release_authorized":False,
        "remaining_gate":"independent_cross_principal_canary_and_operator_approval",
        "mode":"staging" if args.allow_inactive else "production",
        "checks":[item.__dict__ for item in checks],
    },sort_keys=True,indent=2))
    return 0 if ok else 2


if __name__=="__main__":
    raise SystemExit(main())
