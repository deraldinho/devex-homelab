"""Dispatch auditable OpenCode PLAN sessions for Atlas CP26-31.

Local only; no remote execution, no deployment, and no credential logging.
Session creation and prompt submission are never retried automatically.
"""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import sys
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / ".atlas" / "opencode" / "cp26-cp31"
BASE = "http://127.0.0.1:49374"
MISSIONS = {
    "cp26-security": (
        "opencode", "mimo-v2.6-flash-free",
        "Atlas CP26 security review: inspect infrastructure/pentium/dashboard/atlas_dashboard.py, "
        "dashboard_chat.py, and deployment config. Find whether POST /api/chat accepts anonymous LAN "
        "requests and identify highest-risk impact. Read only; do not execute POST or read credentials. "
        "Return evidence-based failing regression tests and precise remediation proposal. "
        "NO editing, deploy, branch, worktree, commit or push."
    ),
    "cp27-dr": (
        "opencode", "ling-3.1-flash-free",
        "Atlas CP27 read-only release and disaster-recovery audit. Inspect existing "
        "infrastructure/backup and tools/atlas_*deploy* plus docs/as-built DR reports. "
        "Identify minimal safe next actions for reproducing release and restoring offsite "
        "without touching production data. Reconcile 113 preexisting dirty files; "
        "do NOT clean, write, commit, push, deploy, or run any destructive tests."
    ),
    "cp28-transport": (
        "opencode", "nemotron-3.5-lightning-free",
        "Atlas CP28 independent read-only architecture review: inspect "
        "infrastructure/core/agency-agents and infrastructure/pentium/atlas agency_specialists "
        "and existing tests. Find verified typed transport, durable receipts, permissions, "
        "and recovery gaps for Core worker; propose smallest TDD implementation slices. "
        "Do not edit files, run shell, expose .env, commit, deploy, branch or worktree."
    ),
    "cp26-chat-independent-qa": (
        "opencode", "nemotron-3.5-lightning-free",
        "Independent CP26 security and regression reviewer. READ ONLY: inspect "
        "infrastructure/pentium/dashboard/atlas_dashboard.py and "
        "tests/test_cp26_chat_peer_security.py; review peer-IP authorization, "
        "SSH-forward semantics, X-Forwarded-For, origin/CSRF, IPv4-mapped IPv6, "
        "bound addresses and any overlooked bypass. Also inspect "
        "infrastructure/pentium/atlas/conversational_fallback.py and "
        "reaction_loop_cognitivo.py for accidental capability authorization "
        "from natural prose. Return precise security findings and proposed RED "
        "tests; do not edit, deploy, commit, push or read credentials."
    ),
    "cp28-receipt-ledger-build": (
        "opencode", "nemotron-3.5-lightning-free",
        "CP28 BUILD small, pure TDD slice: create ONLY "
        "infrastructure/pentium/atlas/agency_receipt_ledger.py and "
        "infrastructure/pentium/atlas/tests/test_agency_receipt_ledger.py. "
        "Implement isolated durable SQLite receipts (idempotency key, task_id, "
        "specialist id, state lifecycle, correlation_id, bounded sanitized "
        "summary, timestamps, retry provenance) with strict read-only event "
        "contract, transactions and uniqueness constraints. Reject actions, "
        "untrusted paths and unknown fields; no prod integration, no migration, "
        "no credentials. TDD + concurrency/duplicate tests; no commit, push, "
        "deploy, branch, worktree or changing existing files."
    ),
    "cp27-release-inventory-build": (
        "opencode", "nemotron-3.5-lightning-free",
        "CP27 BUILD implementation: create ONLY tools/atlas_cp27_release_inventory.py "
        "and tools/test_atlas_cp27_release_inventory.py. Implement read-only "
        "inventory of dirty Git paths and hashes with safe bounded output, "
        "reject symlinks/path traversal and avoid reading file contents or secrets. "
        "TDD, no arbitrary shell, no changes to preexisting code, no commit, "
        "push, deploy, restart, branch or worktree. Cite tests and exit code."
    ),
    "cp30-graph-contract-build": (
        "opencode", "mimo-v2.6-flash-free",
        "CP30 BUILD implementation: create ONLY "
        "infrastructure/pentium/atlas/memory_graph_v2_contracts.py and "
        "infrastructure/pentium/atlas/tests/test_memory_graph_v2_contracts.py. "
        "Implement a small strictly typed, versioned MemoryGraph v2 event/node "
        "schema validator with provenance, bounded payload and rejection tests. "
        "No migration or writing persistent data; preserve all existing modules. "
        "TDD, no commit, push, deploy, restart, branch, secrets or worktree."
    ),
    "cp27-dr-fallback": (
        "opencode", "nemotron-3.5-lightning-free",
        "Atlas CP27 read-only release and disaster-recovery audit. Inspect existing "
        "infrastructure/backup, tools/atlas_*deploy* and DR as-built reports. "
        "Identify safe next steps for reproducible releases and isolated/offsite restore. "
        "The previous Ling model had a terminal provider.no-route failure. "
        "Do not modify files, access secrets, invoke deploy or restart hosts."
    ),
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("OpenCode redirect refused")


BUILD_MISSIONS = frozenset(("cp27-release-inventory-build", "cp30-graph-contract-build", "cp28-receipt-ledger-build"))


def api(method: str, path: str, payload: dict | None = None) -> dict:
    if not path.startswith("/api/") or ".." in path or "?" in path:
        raise ValueError("Unapproved endpoint")
    secret_file = Path.home() / ".config" / "opencode" / "service.json"
    password = json.loads(secret_file.read_text(encoding="utf-8-sig"))["password"]
    if not isinstance(password, str) or not password:
        raise RuntimeError("OpenCode local password not configured")
    token = base64.b64encode(("opencode:" + password).encode()).decode()
    request = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": "Basic " + token, "Accept": "application/json",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            data = response.read(1000000)
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError("OpenCode HTTP " + str(exc.code)) from None

def save(path: Path, receipt: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)

def dispatch(name: str) -> None:
    if name not in MISSIONS:
        raise ValueError("Unknown allowlisted mission")
    if name == "cp27-dr-fallback":
        original = RECEIPTS / "cp27-dr.json"
        if not original.is_file():
            raise RuntimeError("Original CP27 receipt not found")
        sid = json.loads(original.read_text(encoding="utf-8")).get("session_id")
        if not isinstance(sid, str) or not sid.startswith("ses_"):
            raise RuntimeError("Original CP27 session not identified")
        state = api("GET", "/api/session/" + sid).get("data", {})
        messages = api("GET", "/api/session/" + sid + "/message").get("data", [])
        errors = [msg.get("error", {}).get("type") for msg in messages
                  if isinstance(msg, dict) and isinstance(msg.get("error"), dict)]
        if state.get("outcome") != "failed" or "provider.no-route" not in errors:
            raise RuntimeError("CP27 failure not safe to retry")
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    path = RECEIPTS / (name + ".json")
    # An ambiguous error must not create a second agent or replay a prompt.
    with path.open("x", encoding="utf-8") as handle:
        json.dump({"mission": name, "state": "CREATION_UNKNOWN"}, handle)
    provider, model, prompt = MISSIONS[name]
    receipt = {"mission": name, "state": "CREATION_UNKNOWN", "model": provider + "/" + model}
    try:
        info = api("GET", "/api/info")
        receipt["server_version"] = info.get("version")
        if not str(info.get("version", "")).startswith("2.0."):
            raise RuntimeError("OpenCode version not verified")
        session = api("POST", "/api/session", {
            "title": "Atlas-" + name + "-20261015",
            "agent": "build" if name in BUILD_MISSIONS else "plan",
            "model": {"providerID": provider, "id": model, "variant": "default"},
            "location": {"directory": str(ROOT)},
        }).get("data", {})
        sid = session.get("id")
        location = session.get("location", {}).get("directory")
        if not isinstance(sid, str) or not sid.startswith("ses_"):
            raise RuntimeError("Session ID missing")
        receipt["session_id"] = sid
        receipt["state"] = "CREATED_UNDISPATCHED"
        save(path, receipt)
        if not isinstance(location, str) or Path(location).resolve() != ROOT.resolve():
            raise RuntimeError("Wrong repo: stop without prompt")
        receipt["state"] = "PROMPT_UNKNOWN"
        save(path, receipt)
        api("POST", "/api/session/" + sid + "/prompt", {"text": prompt})
        receipt["state"] = "PROMPT_ACKNOWLEDGED_UNVERIFIED"
        save(path, receipt)
    except Exception as exc:
        receipt["error_type"] = type(exc).__name__
        save(path, receipt)
    print(json.dumps(receipt, ensure_ascii=False))

def reconcile(name: str) -> None:
    """Persist *session* terminal state without claiming QA or release success."""
    if name not in MISSIONS:
        raise ValueError("Unknown allowlisted mission")
    path = RECEIPTS / (name + ".json")
    if not path.is_file():
        raise ValueError("Receipt not found")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("mission") != name:
        raise ValueError("Receipt identity mismatch")
    if receipt.get("state") in (
        "SESSION_SUCCEEDED", "SESSION_FAILED", "SESSION_CANCELLED"
    ):
        print(json.dumps(receipt, ensure_ascii=False))
        return
    sid = receipt.get("session_id")
    if not isinstance(sid, str) or not sid.startswith("ses_"):
        raise ValueError("Session identity missing")
    remote = api("GET", "/api/session/" + sid).get("data", {})
    result = remote.get("outcome") if isinstance(remote, dict) else None
    # A session with no outcome, an unfamiliar outcome, or a different ID is
    # still ambiguous. Never infer success from HTTP 200 alone.
    allowed = {"succeeded": "SESSION_SUCCEEDED",
               "failed": "SESSION_FAILED",
               "cancelled": "SESSION_CANCELLED"}
    if isinstance(remote, dict) and remote.get("id") == sid and result in allowed:
        receipt["server_outcome"] = result
        receipt["state"] = allowed[result]
        save(path, receipt)
    print(json.dumps(receipt, ensure_ascii=False))


def status(name: str) -> None:
    path = RECEIPTS / (name + ".json")
    if not path.is_file():
        print(json.dumps({"mission": name, "state": "NOT_DISPATCHED"}))
        return
    receipt = json.loads(path.read_text(encoding="utf-8"))
    sid = receipt.get("session_id")
    if isinstance(sid, str) and sid.startswith("ses_"):
        try:
            remote = api("GET", "/api/session/" + sid).get("data", {})
            receipt["server_outcome"] = remote.get("outcome", "UNDECLARED")
            receipt["server_status"] = remote.get("status", "UNDECLARED")
        except Exception as exc:
            receipt["poll_error"] = type(exc).__name__
    print(json.dumps(receipt, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("dispatch", "status", "reconcile"):
        raise SystemExit("Usage: python tools/atlas_cp26_cp31_dispatch.py <dispatch|status|reconcile> <mission>")
    {"dispatch": dispatch, "status": status, "reconcile": reconcile}[sys.argv[1]](sys.argv[2])
