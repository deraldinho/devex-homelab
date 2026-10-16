"""Fail-closed OpenCode mission completion evidence (CP22 staging only).

Never treats an API-accepted prompt, a running process, or a plan-mode
session as evidence that source code was implemented.
"""
from collections.abc import Mapping

TERMINAL = frozenset(("succeeded",))
ALLOWED_IMPLEMENTATION_AGENTS = frozenset(("build",))


def verify_implementation(session, *, expected_project, required_files, file_exists):
    """Evaluate session metadata plus independently verified filesystem effects."""
    reasons = []
    if not isinstance(session, Mapping):
        session = {}
        reasons.append("INVALID_SESSION")
    if not isinstance(expected_project, str) or not expected_project.strip():
        raise ValueError("expected_project required")
    if not isinstance(required_files, (tuple, list)) or not required_files:
        raise ValueError("required_files must be nonempty list")
    if session.get("outcome") not in TERMINAL:
        reasons.append("NO_SUCCESSFUL_TERMINAL_OUTCOME")
    if session.get("agent") not in ALLOWED_IMPLEMENTATION_AGENTS:
        reasons.append("NOT_BUILD_AGENT")
    location = session.get("location")
    directory = location.get("directory") if isinstance(location, Mapping) else None
    if not isinstance(directory, str) or directory.casefold().rstrip("\\/") != expected_project.casefold().rstrip("\\/"):
        reasons.append("PROJECT_MISMATCH")
    if not callable(file_exists):
        raise TypeError("file_exists callback required")
    for name in required_files:
        if not isinstance(name, str) or not name.strip() or "/" in name or "\\" in name or name in (".", ".."):
            reasons.append("INVALID_ARTIFACT_NAME")
            continue
        try:
            present = file_exists(name) is True
        except Exception:
            present = False
        if not present:
            reasons.append("ARTIFACT_UNVERIFIED:" + name)
    return {"verified": not reasons, "production_allowed": False, "reasons": reasons}
