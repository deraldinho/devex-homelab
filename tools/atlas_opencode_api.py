"""Atlas -> OpenCode via private Tailscale HTTPS API.

Only the project-local inbox task is sent, and only the matching outbox report
is accepted. No arbitrary remote endpoint or command execution.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping


VPN_URL = "https://x99.tail2ffe44.ts.net"
TASK_ID_PATTERN = re.compile(r"^\d{8}T\d{6}Z-[a-f0-9]{8}$")
SESSION_ID_PATTERN = re.compile(r"^ses_[a-zA-Z0-9]+$")
MAX_TASK_BYTES = 24_000
MAX_REPORT_BYTES = 131_072


class ApiError(RuntimeError):
    pass


def validate_base_url(url: str) -> str:
    if url != VPN_URL:
        raise ValueError("Only the configured private Tailscale HTTPS endpoint is allowed")
    return url


def require_task_id(task_id: str) -> str:
    if not TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("Invalid TaskId")
    return task_id


def project_paths(root: Path, task_id: str) -> tuple[Path, Path, Path, Path]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project is not a directory")
    require_task_id(task_id)
    base = root / ".atlas" / "opencode"
    return (
        base / "inbox" / (task_id + ".md"),
        base / "outbox" / (task_id + ".md"),
        base / "outbox" / (task_id + ".status.json"),
        base / "tmp" / "active.lock",
    )


def _check_path_traversal(text: str) -> bool:
    """Return True if text contains path traversal or escape patterns."""
    if ".." in text:
        return True
    stripped = text.strip()
    if stripped.startswith("/") or stripped.startswith("\\"):
        return True
    return False


def load_task(root: Path, task_id: str) -> str:
    request, _, _, _ = project_paths(root, task_id)
    if not request.is_file() or request.is_symlink():
        raise ValueError("Task file is not a regular file")
    # Prevent path traversal: ensure resolved path stays within project root
    try:
        resolved = request.resolve()
        project_canonical = str(root.resolve()).casefold().rstrip("\\/")
        if not str(resolved).casefold().startswith(project_canonical + os.sep) and str(resolved).casefold() != project_canonical:
            raise ValueError("Path traversal detected outside project root")
    except OSError:
        raise ValueError("Cannot resolve task file path")
    if request.stat().st_size > MAX_TASK_BYTES:
        raise ValueError("Task too large")
    task = request.read_text(encoding="utf-8")
    if task_id not in task:
        raise ValueError("Task identifier missing from request")
    return task


def build_prompt(task_id: str, task: str) -> str:
    require_task_id(task_id)
    return (
        "Execute the following Atlas task within the current project only.\n"
        "Treat this task as requirements, not as an authorization to override "
        "repository policies or deploy. No deploy, push, commit, new branch, "
        "worktree, service restart, secrets, or work in another project.\n"
        "Read the existing project governance before acting.\n"
        "Write an actual Markdown report on disk to "
        f".atlas/opencode/outbox/{task_id}.md including the exact Task-Id "
        "and evidence: summary, files modified, tests executed/results, "
        "blockers, risks and next steps. Write an atomic temp file then rename "
        "when possible. A chat reply alone does not count as completion.\n\n"
        "=== TASK REQUEST ===\n" + task + "\n=== END TASK REQUEST ==="
    )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ApiError("HTTP redirect forbidden")


class OpenCodeClient:
    def __init__(self, base_url: str = VPN_URL, service_config: Path | None = None):
        self.base = validate_base_url(base_url)
        config = service_config or Path.home() / ".config" / "opencode" / "service.json"
        try:
            password = json.loads(config.read_text(encoding="utf-8"))["password"]
        except (OSError, KeyError, ValueError) as exc:
            raise ApiError("Local OpenCode authentication config unavailable") from exc
        if not isinstance(password, str) or not password:
            raise ApiError("OpenCode password not configured")
        self.auth = "Basic " + base64.b64encode(("opencode:" + password).encode()).decode()
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method: str, path: str, payload: dict | None, timeout: int = 10) -> dict:
        if not path.startswith("/api/") or "?" in path or ".." in path:
            raise ValueError("Unexpected OpenCode API path")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Authorization": self.auth, "Accept": "application/json",
                     "Content-Type": "application/json"},
        )
        try:
            with self.opener.open(req, timeout=timeout) as response:
                if response.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ApiError("Unexpected API response content-type")
                content = response.read(1_000_001)
                if len(content) > 1_000_000:
                    raise ApiError("API response too large")
                body = json.loads(content.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ApiError("Malformed API response")
                return body
        except urllib.error.HTTPError as exc:
            raise ApiError(f"HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ApiError("API connection or timeout error") from None
        except (ValueError, UnicodeError):
            raise ApiError("Malformed API response") from None

    def post(self, path: str, obj: dict | None = None, timeout: int = 10) -> dict:
        return self.request("POST", path, obj, timeout)

    def get(self, path: str, timeout: int = 10) -> dict:
        return self.request("GET", path, None, timeout)


def unwrap_data(response: dict) -> dict:
    """Extract the "data" dict from an API response."""
    data = response.get("data", response)
    if not isinstance(data, dict):
        raise ApiError("Malformed API data")
    return data


def verify_session_agent_and_location(
    session: dict,
    project_root: Path,
    *,
    required_agent: str = "build",
) -> list[str]:
    """Verify that a session has the expected agent and matches the project root.

    Returns a list of reason strings; empty list means verification passed.
    """
    reasons: list[str] = []
    if not isinstance(session, Mapping):
        reasons.append("INVALID_SESSION")
        return reasons
    agent = session.get("agent")
    if not isinstance(agent, str) or agent != required_agent:
        reasons.append("NOT_BUILD_AGENT")
    location = session.get("location")
    directory = location.get("directory") if isinstance(location, Mapping) else None
    if not isinstance(directory, str):
        reasons.append("MISSING_LOCATION_DIRECTORY")
    else:
        project_canonical = str(project_root.resolve()).casefold().rstrip("\\/")
        session_canonical = directory.casefold().rstrip("\\/")
        if session_canonical != project_canonical:
            reasons.append("PROJECT_MISMATCH")
    return reasons


def report_is_complete(path: Path, task_id: str) -> bool:
    """Require a bounded, substantive report with the mandatory sections.

    A report remains a claim, not proof that tests/deploy succeeded. Its
    structure merely prevents 'Task-Id only' or empty reports being accepted.

    The Task-Id header must match exactly: the first line must be
    "# Task-Id: <task_id>".  This prevents a malformed header from being
    accepted while still accepting the standard report format produced by
    complete_report().
    """
    if path.is_symlink() or not path.is_file():
        return False
    try:
        size = path.stat().st_size
        if not 0 < size <= MAX_REPORT_BYTES:
            return False
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False

    # ---- Exact Task-Id header check (strengthened) ----
    # The first line must be exactly "# Task-Id: <task_id>".
    # This is stricter than "task_id in contents[:512]" while still
    # accepting the standard format produced by complete_report().
    lines = contents.splitlines()
    if not lines or lines[0].strip() != "# Task-Id: " + task_id:
        return False

    def normalize(value: str) -> str:
        return "".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                       if not unicodedata.combining(char)).strip()

    sections = {}
    current = None
    for line in contents.splitlines():
        if line.startswith("## "):
            current = normalize(line[3:])
            sections.setdefault(current, "")
        elif current and line.strip():
            sections[current] += line.strip()
    required = {"resumo", "arquivos alterados", "testes",
                "bloqueios e riscos", "proximos passos"}
    return all(len(sections.get(heading, "")) >= 6 for heading in required)


def _normalize_artifact_path(path_str: str) -> str | None:
    """Normalize an artifact path segment.

    Returns:
        - "NENHUM" if the path indicates no artifacts (e.g. "Nenhum.", "none")
        - None if the path is unsafe (absolute, contains traversal)
        - The cleaned path string otherwise
    """
    if not path_str:
        return None
    s = path_str.strip()
    # Absolute escape
    if s.startswith("/") or s.startswith("\\"):
        return None
    # Path traversal
    if ".." in s:
        return None
    # No-artifacts sentinel: strip trailing punctuation then compare
    stripped = s.rstrip(".,:;!")
    if stripped.casefold() in ("nenhum", "none", ""):
        return "NENHUM"
    return s


def _parse_manifest_from_task(task_id: str, root: Path) -> tuple[list[str], bool]:
    """Parse the required-artifacts manifest from an inbox task.

    Only the ```required-artifacts``` fenced block is recognized.
    Other Markdown code fences (```python, ```bash, etc.) are ignored.
    The manifest content is parsed as space- or newline-separated paths.

    Returns:
        - (paths, has_manifest): paths is a list of artifact path strings,
          has_manifest is True if a ```required-artifacts``` block was found
          in the inbox task file.
        - If the manifest contains only "Nenhum." or is empty, paths is [] and
          has_manifest is True (the block existed but declared no artifacts).
        - On malformed or unrecognised fencing, fails closed: returns ([], False).
    """
    inbox_dir = root / ".atlas" / "opencode" / "inbox"
    task_file = inbox_dir / (task_id + ".md")
    if not task_file.is_file():
        return [], False
    try:
        text = task_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return [], False

    # ------------------------------------------------------------------
    # Locate ONLY ```required-artifacts``` blocks.  Any other ``` fence
    # is ignored – the parser toggles solely on the exact identifier.
    # ------------------------------------------------------------------
    IN_REQUIRED = "<REQUIRED_ARTEFACTS>"   # sentinel, never appears in real text
    state = "outside"                      # outside | inside
    manifest_lines: list[str] = []
    found_block = False                      # became True if we ever saw ```

    for line in text.splitlines():
        stripped = line.strip()

        # Check for the exact required-artifacts fence opening
        if stripped == "```required-artifacts":
            if state == "outside":
                state = "inside"
                found_block = True
                continue
            # closing fence while already inside – treat as content line
            if state == "inside":
                state = "outside"
                continue

        # Check for the exact required-artifacts fence closing
        if stripped == "```":
            if state == "inside":
                state = "outside"
                continue
            # fence outside the required block – ignore
            continue

        # If we are inside a required-artifacts block, collect lines
        if state == "inside":
            manifest_lines.append(stripped)

    # ------------------------------------------------------------------
    # No ```required-artifacts``` block found at all → fail closed
    # ------------------------------------------------------------------
    if not found_block:
        return [], False

    # ------------------------------------------------------------------
    # Parse the collected lines
    # ------------------------------------------------------------------
    raw_paths = [p for p in manifest_lines if p.strip()]

    if not raw_paths:
        # Manifest block existed (```required-artifacts``` was found) but is empty
        return [], True

    # Manifest block had content – split on whitespace to get tokens
    paths: list[str] = []
    seen: set[str] = set()
    for token in " ".join(raw_paths).split():
        cleaned = token.strip("-*• ").strip()
        norm = _normalize_artifact_path(cleaned)
        if norm is None:
            # Unsafe path (absolute or traversal) – record as-is for rejection
            if cleaned not in seen:
                paths.append(cleaned)
                seen.add(cleaned)
        elif norm == "NENHUM":
            # Sentinel "Nenhum." in manifest means no artifacts
            return [], True
        else:
            if norm not in seen:
                paths.append(norm)
                seen.add(norm)

    return paths, True


def _is_safe_in_repo_regular_file(path_str: str, project_root: Path) -> bool:
    """Check whether *path_str* resolves to a safe in-repo regular file.

    Safetly checks:
      • not absolute
      • no traversal that escapes the project root
      • the resolved path is under project_root
      • the file exists and is a regular file (not a symlink)
    """
    try:
        # Build the full path relative to project root
        full = (project_root / path_str).resolve()
        proj = project_root.resolve()
        # Must be under project root
        full_str = str(full)
        proj_str = str(proj)
        if not (full_str == proj_str or full_str.startswith(proj_str + os.sep)):
            return False
        # Must be a regular file and not a symlink
        if not full.is_file() or full.is_symlink():
            return False
        return True
    except (OSError, ValueError):
        return False


def verify_artifacts_for_build(task_id: str, report: Path, project_root: Path) -> list[str]:
    """Opt-in artifact verification for build implementations only.

    Returns a list of reason strings; empty list means verification passed.
    This is intentionally not enforced for read-only review agents.

    What it does:
      • Ensures the report has a '## Arquivos alterados' section
      • Parses the section content;  'Nenhum.' / empty → pass (no artifacts)
        ONLY if no manifest is declared in the inbox task.
      • If a required-artifacts manifest exists in the inbox task, its paths
        take precedence;  'Nenhum.' in the report cannot bypass declared paths.
      • For each declared artifact path (from manifest or report):
          – rejects absolute escapes
          – rejects path traversal (..)
          – rejects symlinks
          – verifies the file is a regular in-repo file
      • Does NOT claim preexisting files were created by this run
        (it only attests the file is a safe normalized in-repo regular file).
    """
    reasons: list[str] = []
    if not report.is_file() or report.is_symlink():
        reasons.append("MISSING_OR_INVALID_REPORT")
        return reasons
    try:
        contents = report.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        reasons.append("READ_ERROR")
        return reasons

    # -- 0. Check for required-artifacts manifest in the inbox task -------
    manifest_paths, has_manifest = _parse_manifest_from_task(task_id, project_root)

    if has_manifest and manifest_paths:
        # Manifest declares paths → report Nenhum. cannot bypass them
        for artifact in manifest_paths:
            if not _is_safe_in_repo_regular_file(artifact, project_root):
                reasons.append(f"INVALID_ARTIFACT: {artifact}")
        if reasons:
            return reasons  # manifest paths invalid → fail
        # Manifest paths are all valid; report content is secondary
        # (declaration satisfied, proceed to report completeness check)
        return reasons  # empty → pass

    # -- 1. Section presence check (opt-in for build agents) -------------
    if "## Arquivos alterados" not in contents:
        reasons.append("MISSING_ARTIFACT_SECTION")
        return reasons

    # -- 2. Parse the section content -------------------------------------
    in_artifacts = False
    section_parts: list[str] = []
    for line in contents.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            header = stripped[3:].strip().casefold()
            in_artifacts = header == "arquivos alterados"
            continue
        if in_artifacts:
            section_parts.append(stripped)

    # Join all artifact-line fragments into one string and split on whitespace
    raw_section = " ".join(section_parts).strip()

    # If nothing declared or the sentinel "Nenhum." / "none" → pass, no artifacts
    clean_raw = raw_section.rstrip(".,:;!")
    if not raw_section or clean_raw.casefold() in ("nenhum", "none"):
        return reasons  # empty reasons → verification passed

    # Break into individual path candidates: split on whitespace, strip bullets
    raw_candidates: list[str] = []
    for token in raw_section.split():
        # Remove common list markers (- * •)
        cleaned = token.strip("-*• ").strip()
        norm = _normalize_artifact_path(cleaned)
        if norm is None:
            # Unsafe path (absolute or traversal) – record and skip
            reasons.append(f"UNSAFE_ARTIFACT_PATH: {cleaned}")
            continue
        if norm == "NENHUM":
            # Sentinel means "no artifacts" – treat as pass
            return reasons
        raw_candidates.append(norm)

    # -- 3. Validate each artifact path -------------------------------------
    for artifact in raw_candidates:
        if not _is_safe_in_repo_regular_file(artifact, project_root):
            reasons.append(f"INVALID_ARTIFACT: {artifact}")

    return reasons


def atomic_json(path: Path, payload: dict) -> None:
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".partial")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def wait_for_project_lock(lockfile: Path, task_id: str, deadline: float) -> bool:
    """Atomically wait for a project lock; never steal or delete another task's lock.

    Deadline is an absolute monotonic time, including time spent in queue.
    """
    while True:
        try:
            with lockfile.open("x", encoding="utf-8") as lock:
                lock.write(task_id)
            return True
        except FileExistsError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.3, remaining))


class ApiRunner:
    def __init__(self, client, root: Path, task_id: str,
                 timeout_seconds: int = 900, model: str = ""):
        self.client = client
        self.root = Path(root).resolve(strict=True)
        self.task_id = require_task_id(task_id)
        if not 10 <= timeout_seconds <= 900:
            raise ValueError("Invalid timeout")
        if model and not re.fullmatch(r"[a-zA-Z0-9.-]+-free", model):
            raise ValueError("Only verified OpenCode free models accepted")
        self.timeout_seconds = timeout_seconds
        self.model = model

    def run(self) -> dict:
        task = load_task(self.root, self.task_id)
        _, report, status_file, lockfile = project_paths(self.root, self.task_id)
        if status_file.exists() or report.exists():
            raise FileExistsError("Task already attempted or reported")
        lockfile.parent.mkdir(parents=True, exist_ok=True)
        status_file.parent.mkdir(parents=True, exist_ok=True)

        # Waiting for the shared project gate is included in the time budget.
        # Exclusivity uses O_EXCL (open x), not a check-then-write race.
        started = time.time()
        deadline = time.monotonic() + self.timeout_seconds
        if not wait_for_project_lock(lockfile, self.task_id, deadline):
            status = {
                "task_id": self.task_id, "state": "busy", "session_id": None,
                "report_exists": False,
                "started_at_unix": started, "finished_at_unix": time.time(),
            }
            atomic_json(status_file, status)
            return status
        state = "api_error"
        session_id = None
        try:
            body = {
                "title": "Atlas task " + self.task_id,
                "agent": "build",
                "location": {"directory": str(self.root)},
            }
            if self.model:
                body["model"] = {"providerID": "opencode", "id": self.model}
            info = unwrap_data(self.client.post("/api/session", body, timeout=15))
            session_id = info.get("id")
            if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
                raise ApiError("Session creation yielded invalid session ID")
            # Durable session link before submitting prompt; safe to recover if interrupted.
            atomic_json(status_file, {
                "task_id": self.task_id, "state": "session_created",
                "session_id": session_id, "report_exists": False,
            })
            # The server may execute synchronously and hold the response.
            # A request timeout is ambiguous: poll the created session, never resend.
            try:
                self.client.post(
                    f"/api/session/{session_id}/prompt",
                    {"text": build_prompt(self.task_id, task)},
                    timeout=min(25, self.timeout_seconds),
                )
            except ApiError as exc:
                if str(exc) != "API connection or timeout error":
                    raise
            state = "waiting"
            while time.monotonic() < deadline:
                data = unwrap_data(
                    self.client.get(f"/api/session/{session_id}", timeout=10)
                )
                outcome = data.get("outcome")
                if outcome in ("succeeded", "failed", "interrupted"):
                    if outcome == "succeeded":
                        state = "completed"
                    else:
                        state = "agent_" + outcome
                    break
                time.sleep(2)
            else:
                state = "timeout"
            if state == "completed":
                reasons = verify_session_agent_and_location(data, self.root)
                if reasons:
                    state = "session_verification_failed"
                else:
                    # Opt-in artifact verification only for build implementations
                    # when a report file independently exists -- identical gate
                    # to run().  When the artifact check passes, proceed to
                    # report_is_complete; otherwise mark invalid_report.
                    if data.get("agent") == "build" and report.is_file() and not report.is_symlink():
                        artifact_reasons = verify_artifacts_for_build(
                            self.task_id, report, self.root
                        )
                        if artifact_reasons:
                            state = "invalid_report"
                        else:
                            if report_is_complete(report, self.task_id):
                                state = "reported"
                            elif report.is_file() and not report.is_symlink():
                                state = "invalid_report"
                            else:
                                state = "missing_report"
                    else:
                        if report_is_complete(report, self.task_id):
                            state = "reported"
                        elif report.is_file() and not report.is_symlink():
                            state = "invalid_report"
                        else:
                            state = "missing_report"
        except (ApiError, ValueError, OSError) as exc:
            state = "api_error"
        finally:
            # Do not remove someone else's lock. The file was created by this invocation.
            if lockfile.is_file() and lockfile.read_text(encoding="utf-8") == self.task_id:
                lockfile.unlink()
            status = {
                "task_id": self.task_id, "state": state,
                "session_id": session_id,
                "report_exists": report.is_file() and not report.is_symlink(),
                "started_at_unix": started, "finished_at_unix": time.time(),
            }
            atomic_json(status_file, status)
        return status

    def reconcile(self) -> dict:
        # Never replay the prompt. Query only the session created by this task.
        _, report, status_file, lockfile = project_paths(self.root, self.task_id)
        if not status_file.is_file() or status_file.is_symlink():
            raise ValueError("Existing task status is required")
        # A report is not accepted while another run owns the project lock.
        if lockfile.exists():
            raise FileExistsError("Project task is still running")
        try:
            old = json.loads(status_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("Malformed existing status") from exc
        if not isinstance(old, dict) or old.get("task_id") != self.task_id:
            raise ValueError("Status TaskId mismatch")
        session_id = old.get("session_id")
        if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ValueError("Invalid prior session identifier")
        if old.get("state") == "reported":
            # Re-verify declared artifacts from the original inbox task,
            # not just the report content.  This prevents bypasses where
            # a previously reported state can be accepted without re-checking
            # the inbox manifest against the canonical project root.
            manifest_paths, has_manifest = _parse_manifest_from_task(
                self.task_id, self.root
            )
            reasons: list[str] = []
            if has_manifest and manifest_paths:
                # Manifest declares paths → verify each artifact is a safe
                # in-repo regular file; report Nenhum. cannot bypass them.
                for artifact in manifest_paths:
                    if not _is_safe_in_repo_regular_file(artifact, self.root):
                        reasons.append(f"INVALID_ARTIFACT: {artifact}")
                if reasons:
                    # Manifest paths invalid → reject the previously reported state
                    old.update({
                        "state": "invalid_report",
                        "report_exists": report.is_file() and not report.is_symlink(),
                        "reconciled_at_unix": time.time(),
                    })
                    atomic_json(status_file, old)
                    return old
            # Even when no manifest, still check report completeness
            # as a secondary gate (opt-in for build agents).
            if not reasons and report_is_complete(report, self.task_id):
                return old
            old.update({
                "state": "invalid_report",
                "report_exists": report.is_file() and not report.is_symlink(),
                "reconciled_at_unix": time.time(),
            })
            atomic_json(status_file, old)
            return old
        # A late report is considered only after confirming a terminal
        # successful outcome. Never resend the original prompt.
        exists = report.is_file() and not report.is_symlink()
        info = unwrap_data(
            self.client.get(f"/api/session/{session_id}", timeout=12)
        )
        outcome = info.get("outcome")
        reasons = verify_session_agent_and_location(info, self.root)
        if outcome == "succeeded" and reasons:
            state = "session_verification_failed"
        elif outcome == "succeeded":
            # Verify declared artifacts from the original inbox task using
            # verify_artifacts_for_build, respecting the agent build and
            # canonical root on every successful state.
            manifest_paths, has_manifest = _parse_manifest_from_task(
                self.task_id, self.root
            )
            if has_manifest and manifest_paths:
                # Manifest declares paths → verify each artifact is a safe
                # in-repo regular file; report Nenhum. cannot bypass them.
                for artifact in manifest_paths:
                    if not _is_safe_in_repo_regular_file(artifact, self.root):
                        reasons.append(f"INVALID_ARTIFACT: {artifact}")
                if not reasons:
                    # All manifest paths are valid; now check report completeness
                    if report_is_complete(report, self.task_id):
                        state = "reported"
                    else:
                        state = "invalid_report"
                else:
                    state = "invalid_report"
            else:
                # No manifest or empty manifest → report check as before
                if report_is_complete(report, self.task_id):
                    state = "reported"
                elif exists:
                    state = "invalid_report"
                elif old.get("state") == "reported":
                    state = "missing_report"
                else:
                    state = "pending"
        elif outcome in ("failed", "interrupted"):
            state = "agent_" + outcome
        else:
            state = "pending"
        old.update({
            "state": state,
            "report_exists": exists,
            "reconciled_at_unix": time.time(),
        })
        atomic_json(status_file, old)
        return old


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atlas project-scoped OpenCode API bridge")
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default=VPN_URL)
    parser.add_argument("--reconcile", action="store_true")
    args = parser.parse_args(argv)
    try:
        client = OpenCodeClient(args.base_url)
        runner = ApiRunner(
            client, args.project, args.task_id,
            timeout_seconds=args.timeout_seconds, model=args.model
        )
        result = runner.reconcile() if args.reconcile else runner.run()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["state"] == "reported" else 2
    except (ValueError, FileExistsError, ApiError, OSError):
        print(json.dumps({"task_id": args.task_id, "state": "launcher_error"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())


class OpenCodeClient:
    def __init__(self, base_url: str = VPN_URL, service_config: Path | None = None):
        self.base = validate_base_url(base_url)
        config = service_config or Path.home() / ".config" / "opencode" / "service.json"
        try:
            password = json.loads(config.read_text(encoding="utf-8"))["password"]
        except (OSError, KeyError, ValueError) as exc:
            raise ApiError("Local OpenCode authentication config unavailable") from exc
        if not isinstance(password, str) or not password:
            raise ApiError("OpenCode password not configured")
        self.auth = "Basic " + base64.b64encode(("opencode:" + password).encode()).decode()
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method: str, path: str, payload: dict | None, timeout: int = 10) -> dict:
        if not path.startswith("/api/") or "?" in path or ".." in path:
            raise ValueError("Unexpected OpenCode API path")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Authorization": self.auth, "Accept": "application/json",
                     "Content-Type": "application/json"},
        )
        try:
            with self.opener.open(req, timeout=timeout) as response:
                if response.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ApiError("Unexpected API response content-type")
                content = response.read(1_000_001)
                if len(content) > 1_000_000:
                    raise ApiError("API response too large")
                body = json.loads(content.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ApiError("Malformed API response")
                return body
        except urllib.error.HTTPError as exc:
            raise ApiError(f"HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Do not leak server output, secrets or request headers.
            raise ApiError("API connection or timeout error") from None
        except (ValueError, UnicodeError) as exc:
            raise ApiError("Malformed API response") from None

    def post(self, path: str, obj: dict | None = None, timeout: int = 10) -> dict:
        return self.request("POST", path, obj, timeout)

    def get(self, path: str, timeout: int = 10) -> dict:
        return self.request("GET", path, None, timeout)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ApiError("HTTP redirect forbidden")