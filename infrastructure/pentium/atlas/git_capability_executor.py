from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


class GitCapabilityExecutor:
    def __init__(self, repo_roots: dict[str, Path] | None = None, *, runner=subprocess.run):
        self._runner = runner
        self._roots = dict(repo_roots or {})

    def _resolve_repo(self, project: str) -> Path | None:
        p_clean = str(project).strip().lower().replace("-", "").replace("_", "")
        for key, path in self._roots.items():
            k_clean = key.lower().replace("-", "").replace("_", "")
            if p_clean in k_clean or k_clean in p_clean:
                if path.is_dir() and (path / ".git").is_dir():
                    return path
        # Fallback para caminhos padrão no Pentium
        candidates = [
            Path.home() / "DevEx-HomeLab",
            Path.home() / "pentium-agent",
            Path.home() / "c5-runtime-repo-next",
            Path.home() / "c5-runtime-repo",
            Path.home() / "L2jToren",
            Path("/home/deraldinho/DevEx-HomeLab"),
        ]
        for c in candidates:
            if c.is_dir() and (c / ".git").is_dir():
                if p_clean in str(c.name).lower().replace("-", "").replace("_", ""):
                    return c
        return None

    def git_get_status(self, project: str) -> dict:
        repo_dir = self._resolve_repo(project)
        if repo_dir is None:
            return {"project": project, "status": "repository_not_found_locally", "clean": True}
        try:
            res = self._runner(
                ["git", "-C", str(repo_dir), "status", "-s", "-b"],
                capture_output=True, text=True, timeout=5.0, check=False,
            )
            output = res.stdout.strip()
            branch = output.splitlines()[0] if output else "unknown"
            modified = [l for l in output.splitlines()[1:] if l.strip()]
            return {
                "project": project,
                "path": str(repo_dir),
                "branch": branch,
                "clean": len(modified) == 0,
                "changes_count": len(modified),
                "summary": output[:256],
            }
        except Exception as exc:
            return {"project": project, "error": str(exc)}

    def git_recent_commits(self, project: str, count: int = 5) -> dict:
        repo_dir = self._resolve_repo(project)
        if repo_dir is None:
            return {"project": project, "commits": [], "status": "repository_not_found_locally"}
        n = max(1, min(int(count or 5), 15))
        try:
            res = self._runner(
                ["git", "-C", str(repo_dir), "log", f"-n{n}", "--oneline"],
                capture_output=True, text=True, timeout=5.0, check=False,
            )
            commits = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            return {"project": project, "path": str(repo_dir), "commits": commits}
        except Exception as exc:
            return {"project": project, "commits": [], "error": str(exc)}

    def __call__(self, capability: str, arguments: dict[str, object], _plan=None, _action=None):
        args = dict(arguments or {})
        project = str(args.get("project") or "devex-homelab")
        if capability == "git_get_status":
            return self.git_get_status(project)
        if capability == "git_recent_commits":
            return self.git_recent_commits(project, int(args.get("count") or 5))
        raise PermissionError(f"capability {capability} not handled by GitCapabilityExecutor")


class ClusterVitalsExecutor:
    def __init__(self, state_dir: Path | None = None, *, runner=subprocess.run):
        self._state_dir = Path(state_dir) if state_dir else Path.home() / "pentium-agent" / "atlas" / "runtime"
        self._runner = runner

    def get_cluster_vitals(self, host: str) -> dict:
        h = str(host).strip().lower()
        if h == "pentium":
            try:
                load = Path("/proc/loadavg").read_text(encoding="utf-8").strip() if Path("/proc/loadavg").is_file() else "0.0"
                mem = Path("/proc/meminfo").read_text(encoding="utf-8") if Path("/proc/meminfo").is_file() else ""
                free_kb = 0
                for line in mem.splitlines():
                    if line.startswith("MemAvailable:"):
                        free_kb = int(line.split()[1])
                        break
                return {
                    "host": "pentium",
                    "role": "cognitive_lobo_central",
                    "status": "healthy",
                    "load_avg": load[:16],
                    "mem_available_mb": round(free_kb / 1024, 1),
                }
            except Exception as exc:
                return {"host": "pentium", "status": "error", "detail": str(exc)}

        # Consultar cache de observação dos nós irmãos (core, x99)
        obs_file = self._state_dir / "cognitive-observation-context.json"
        if obs_file.is_file():
            try:
                data = json.loads(obs_file.read_text(encoding="utf-8"))
                for change in data.get("recent_changes", ()):
                    if change.get("source") == h:
                        return {
                            "host": h,
                            "status": change.get("kind", "healthy"),
                            "severity": change.get("severity", "info"),
                            "last_seen": change.get("timestamp"),
                            "monitored": True,
                        }
            except Exception:
                pass

        return {"host": h, "status": "healthy_observed", "monitored": True}

    def __call__(self, capability: str, arguments: dict[str, object], _plan=None, _action=None):
        args = dict(arguments or {})
        host = str(args.get("host") or "pentium")
        if capability == "get_cluster_vitals":
            return self.get_cluster_vitals(host)
        raise PermissionError(f"capability {capability} not handled by ClusterVitalsExecutor")
