from __future__ import annotations

import re
from pathlib import Path

from .capability_registry import atlas_capability_registry
from .policy_capabilities import PolicyCapabilities
from .token_budget_governor import TokenBudgetGovernor
from .workspace_broker import WorkspaceBroker, WorkspaceBrokerError
from .workspace_policy import WorkspacePolicy, WorkspacePolicyError, resolve_workspace_path


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class WorkspaceCertification:
    def __init__(self, root: Path):
        self.root = Path(root)

    @staticmethod
    def _blocked(callable_) -> bool:
        try:
            callable_()
        except (WorkspacePolicyError, WorkspaceBrokerError, PermissionError, ValueError):
            return True
        return False

    def run(self, *, expected_sha: str) -> dict:
        if not isinstance(expected_sha, str) or not _SHA_RE.fullmatch(expected_sha.lower()):
            raise ValueError("expected_sha_invalid")
        policy = WorkspacePolicy()
        broker = WorkspaceBroker(self.root / "workspace", policy)
        registry = atlas_capability_registry()
        capability_policy = PolicyCapabilities(registry)
        governor = TokenBudgetGovernor(window_budget=100)
        governor.record(100, category="self_work")

        quota_broker = WorkspaceBroker(
            self.root / "quota-workspace",
            WorkspacePolicy(max_total_bytes=3, max_file_bytes=3, max_files=1),
        )
        checks = {
            "traversal_blocked": self._blocked(lambda: resolve_workspace_path(broker.root, "notes", "../escape.md", policy)),
            "internal_area_blocked": self._blocked(lambda: resolve_workspace_path(broker.root, ".system", "manifest.json", policy)),
            "executable_blocked": self._blocked(lambda: resolve_workspace_path(broker.root, "notes", "run.sh", policy)),
            "quota_blocked": self._blocked(lambda: quota_broker.write("notes", "x.md", "four")),
            "purge_not_autonomous": not capability_policy.avaliar("workspace_purge", {"trash_id": "x"}).autorizada,
            "no_generic_shell_or_filesystem": not any(name in registry.listar() for name in ("shell", "execute_file", "filesystem_read", "filesystem_write")),
            "human_priority_preserved": governor.allow("human"),
            "incident_priority_preserved": governor.allow("incident"),
        }
        return {
            "schema_version": 1,
            "expected_sha": expected_sha.lower(),
            "passed": all(checks.values()),
            "checks": checks,
        }
