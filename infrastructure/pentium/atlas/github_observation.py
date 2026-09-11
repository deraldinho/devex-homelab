from __future__ import annotations

import json
import re
import subprocess

from .stimulus_model import StimulusSeverity
from .stimulus_sources import SourceSnapshot

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BAD_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}


def _require_repo(repo: str) -> str:
    value = str(repo).strip()
    if not _REPO.fullmatch(value):
        raise ValueError("repository must be owner/name")
    return value


class GitHubCliClient:
    def __init__(self, *, runner=subprocess.run, timeout_s: float = 8.0, per_page: int = 10):
        if timeout_s <= 0 or not 1 <= int(per_page) <= 25:
            raise ValueError("invalid github bounds")
        self._runner = runner
        self._timeout_s = float(timeout_s)
        self._per_page = int(per_page)

    def _get(self, repo: str, suffix: str):
        command = ["gh", "api", f"/repos/{repo}/{suffix}"]
        completed = self._runner(command, capture_output=True, text=True, timeout=self._timeout_s, check=False, shell=False)
        if completed.returncode != 0:
            raise RuntimeError("github api unavailable")
        return json.loads(completed.stdout)

    def repository_snapshot(self, repo: str) -> dict:
        repo = _require_repo(repo)
        pulls = self._get(repo, f"pulls?state=open&per_page={self._per_page}")
        issues = self._get(repo, f"issues?state=open&per_page={self._per_page}")
        runs = self._get(repo, f"actions/runs?per_page={self._per_page}")
        return {
            "repo": repo,
            "pull_requests": [
                {
                    "number": int(item["number"]),
                    "state": str(item.get("state", "")),
                    "draft": bool(item.get("draft", False)),
                    "head_sha": str((item.get("head") or {}).get("sha") or ""),
                    "updated_at": item.get("updated_at"),
                }
                for item in pulls[: self._per_page]
            ],
            "issues": [
                {"number": int(item["number"]), "state": str(item.get("state", "")), "updated_at": item.get("updated_at")}
                for item in issues[: self._per_page] if "pull_request" not in item
            ],
            "workflow_runs": [
                {
                    "id": int(item["id"]),
                    "status": str(item.get("status", "")),
                    "conclusion": item.get("conclusion"),
                    "head_sha": str(item.get("head_sha") or ""),
                    "updated_at": item.get("updated_at"),
                }
                for item in (runs.get("workflow_runs") or [])[: self._per_page]
            ],
        }


class GitHubObservationSource:
    required = False

    def __init__(self, repo: str, client):
        self.repo = _require_repo(repo)
        self.client = client
        self.name = "github." + self.repo.replace("/", ".")

    def poll(self) -> SourceSnapshot:
        payload = self.client.repository_snapshot(self.repo)
        runs = list(payload.get("workflow_runs") or ())
        latest_conclusion = str(runs[0].get("conclusion") or "") if runs else ""
        degraded = latest_conclusion in _BAD_CONCLUSIONS
        payload = dict(payload)
        payload["delivery_healthy"] = not degraded
        status = "degraded" if degraded else "healthy"
        severity = StimulusSeverity.WARNING if degraded else StimulusSeverity.INFO
        return SourceSnapshot(
            source=self.name,
            status=status,
            severity=severity,
            payload=payload,
            fingerprint_payload=payload,
        )


def build_github_sources(repositories, *, client=None):
    gh = client or GitHubCliClient()
    return tuple(GitHubObservationSource(repo, gh) for repo in repositories)
