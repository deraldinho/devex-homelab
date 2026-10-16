"""CP14 offline release gate: fail-closed staging recommendation only.

A pure local/offline evaluator.  It accepts only caller-provided data:

  * a release manifest (change id, target, agent terminality, source
    hashes, diff),
  * HMAC-SHA256 signed, cost-terminal session receipts,
  * an immutable Git workspace fingerprint (commit/tree/file snapshot
    whose digest is recomputed locally),
  * TEST evidence,
  * an independent auditor verdict.

Design guarantees:
  * Fails closed on absent evidence, source hash mismatch, no diff,
    RED tests, an agent that is still inflight, unknown costs, an
    expired receipt, a missing reviewer, a reviewer mismatch and any
    production approval flag.
  * Returns a stable machine reason code plus human readable text.
  * Never declares a deployment of any environment: the strongest
    outcome is ``approved_for_staging`` as a recommendation for a human
    operator.
  * No operating-system command execution, no file or network IO, no
    credential material.  Evidence is inspected, never executed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import re

MANIFEST_SCHEMA = "atlas.release.manifest.v1"
RECEIPT_SCHEMA = "atlas.session.receipt.v1"
WORKSPACE_SCHEMA = "atlas.git.workspace.fingerprint.v1"
TEST_EVIDENCE_SCHEMA = "atlas.test.evidence.v1"
AUDITOR_SCHEMA = "atlas.auditor.verdict.v1"
RESULT_SCHEMA = "atlas.release.gate.result.v1"

HEX64 = re.compile(r"[0-9a-f]{64}")
HEX_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
HEX32 = re.compile(r"[0-9a-f]{32}")
NONCE = re.compile(r"[0-9a-f]{32}")

RECEIPT_BODY_FIELDS = frozenset({
    "schema", "session_id", "agent", "workspace_fingerprint", "issued_at",
    "expires_at", "session_state", "cost", "nonce",
})
RECEIPT_FIELDS = RECEIPT_BODY_FIELDS | {"signature"}

REASON_OK = "OK"
REASON_MISSING_EVIDENCE = "MISSING_EVIDENCE"
REASON_UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
REASON_UNSUPPORTED_TARGET = "UNSUPPORTED_TARGET"
REASON_PRODUCTION_APPROVED = "PRODUCTION_APPROVED_FORBIDDEN"
REASON_WORKSPACE_NOT_IMMUTABLE = "WORKSPACE_NOT_IMMUTABLE"
REASON_WORKSPACE_FINGERPRINT_MISMATCH = "WORKSPACE_FINGERPRINT_MISMATCH"
REASON_SOURCE_HASH_MISMATCH = "SOURCE_HASH_MISMATCH"
REASON_NO_DIFF = "NO_DIFF"
REASON_RECEIPT_SIGNATURE_INVALID = "RECEIPT_SIGNATURE_INVALID"
REASON_RECEIPT_TIME_INVALID = "RECEIPT_TIME_INVALID"
REASON_RECEIPT_EXPIRED = "RECEIPT_EXPIRED"
REASON_RECEIPT_FINGERPRINT_MISMATCH = "RECEIPT_FINGERPRINT_MISMATCH"
REASON_RECEIPT_AGENT_MISMATCH = "RECEIPT_AGENT_MISMATCH"
REASON_AGENT_INFLIGHT = "AGENT_INFLIGHT"
REASON_UNKNOWN_COST = "UNKNOWN_COST"
REASON_TESTS_RED = "TESTS_RED"
REASON_EVIDENCE_FINGERPRINT_MISMATCH = "EVIDENCE_FINGERPRINT_MISMATCH"
REASON_AUDITOR_FINGERPRINT_MISMATCH = "AUDITOR_FINGERPRINT_MISMATCH"
REASON_AUDITOR_REJECTED = "AUDITOR_REJECTED"
REASON_AUDITOR_NOT_INDEPENDENT = "AUDITOR_NOT_INDEPENDENT"
REASON_NO_REVIEWER = "NO_REVIEWER"
REASON_REVIEWER_MISMATCH = "REVIEWER_MISMATCH"
REASON_REVIEWER_NOT_INDEPENDENT = "REVIEWER_NOT_INDEPENDENT"

REASON_TEXT = {
    REASON_OK: "All staging checks passed; recommendation only, no deployment was performed.",
    REASON_MISSING_EVIDENCE: "Required release evidence was not provided; evaluation stops closed.",
    REASON_UNSUPPORTED_SCHEMA: "Evidence uses an unsupported schema version.",
    REASON_UNSUPPORTED_TARGET: "Target environment is not an approved staging target.",
    REASON_PRODUCTION_APPROVED: "Production approval is present; production is out of scope and never approved here.",
    REASON_WORKSPACE_NOT_IMMUTABLE: "Git workspace fingerprint is dirty, malformed or not immutable.",
    REASON_WORKSPACE_FINGERPRINT_MISMATCH: "Declared workspace fingerprint does not match the recomputed snapshot.",
    REASON_SOURCE_HASH_MISMATCH: "Manifest source hashes do not match the workspace snapshot.",
    REASON_NO_DIFF: "The change carries no diff, so there is nothing to release.",
    REASON_RECEIPT_SIGNATURE_INVALID: "Session receipt is unsigned or its signature does not verify.",
    REASON_RECEIPT_TIME_INVALID: "Session receipt timestamps are malformed, naive or issued in the future.",
    REASON_RECEIPT_EXPIRED: "Session receipt has expired.",
    REASON_RECEIPT_FINGERPRINT_MISMATCH: "Session receipt is bound to a different workspace fingerprint.",
    REASON_RECEIPT_AGENT_MISMATCH: "Session receipt was issued to a different agent than the manifest.",
    REASON_AGENT_INFLIGHT: "Agent or session is still inflight; work is not terminal.",
    REASON_UNKNOWN_COST: "Session cost is unknown, non-terminal, non-numeric or in an unknown currency.",
    REASON_TESTS_RED: "TEST evidence is not GREEN or does not cover the full run.",
    REASON_EVIDENCE_FINGERPRINT_MISMATCH: "TEST evidence is bound to a different workspace fingerprint.",
    REASON_AUDITOR_FINGERPRINT_MISMATCH: "Auditor verdict is bound to a different workspace fingerprint.",
    REASON_AUDITOR_REJECTED: "Independent auditor did not approve staging.",
    REASON_AUDITOR_NOT_INDEPENDENT: "Auditor is not independent of the agent that produced the change.",
    REASON_NO_REVIEWER: "No reviewer identity was provided.",
    REASON_REVIEWER_MISMATCH: "Reviewer does not match the reviewer required by the manifest.",
    REASON_REVIEWER_NOT_INDEPENDENT: "Reviewer is not independent of the agent or the auditor.",
}

_SUCCESS_ACTION = ("HUMAN_PROMOTION_REQUIRED: a person promotes this package to staging "
                   "manually; this gate never deploys any environment.")
_BLOCKED_ACTION = "BLOCKED: remediate %s first; this gate never deploys any environment."


def compact(data) -> bytes:
    """Canonical JSON encoding used for hashing and HMAC inputs."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _key(data: bytes) -> bytes:
    if not isinstance(data, bytes) or len(data) != 32:
        raise ValueError("32-byte HMAC key required")
    return data


def _is_file_entry(entry) -> bool:
    return (isinstance(entry, dict)
            and isinstance(entry.get("path"), str) and bool(entry["path"].strip())
            and isinstance(entry.get("sha256"), str)
            and bool(HEX64.fullmatch(entry["sha256"])))


def compute_workspace_fingerprint(*, commit: str, tree: str, files) -> str:
    """Digest of an immutable Git snapshot: head ids plus sorted file hashes.

    Pure and offline; the caller supplies the snapshot contents.
    """
    normalized = sorted(({"path": f["path"], "sha256": f["sha256"]} for f in files),
                        key=lambda item: item["path"])
    return hashlib.sha256(
        compact({"commit": commit, "tree": tree, "files": normalized})
    ).hexdigest()


def sign_session_receipt(*, key: bytes, session_id, agent, workspace_fingerprint,
                         issued_at: datetime, expires_at: datetime,
                         session_state, cost, nonce: str | None = None) -> dict:
    """Produce a signed session receipt for the gate to verify.

    Signing attests provenance and integrity only.  Cost terminality,
    session state, expiry and fingerprint binding are verified
    independently by :func:`evaluate_release`.
    """
    _key(key)
    for label, value in (("issued_at", issued_at), ("expires_at", expires_at)):
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(label + " requires a timezone-aware datetime")
    body = {
        "schema": RECEIPT_SCHEMA,
        "session_id": session_id,
        "agent": agent,
        "workspace_fingerprint": workspace_fingerprint,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "session_state": session_state,
        "cost": cost,
        "nonce": nonce if nonce is not None else hashlib.sha256(
            compact([session_id, agent, issued_at.isoformat()])).hexdigest()[:32],
    }
    body["signature"] = hmac.new(key, compact(body), hashlib.sha256).hexdigest()
    return body


def _cost_error(cost) -> str | None:
    """Return a human explanation when a cost is unknown, else None."""
    if not isinstance(cost, dict):
        return "cost record is not an object"
    if cost.get("terminal") is not True:
        return "cost is not terminal (estimate or missing terminal flag)"
    if cost.get("currency") != "USD":
        return "cost currency is unknown"
    total = cost.get("total_usd")
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        return "cost total is not numeric"
    if total < 0:
        return "cost total is negative"
    return None


def _finalize(approved: bool, code: str, detail: str, checks: list, now: datetime) -> dict:
    return {
        "schema": RESULT_SCHEMA,
        "approved_for_staging": bool(approved),
        "reason": code,
        "reason_text": REASON_TEXT[code],
        "detail": detail,
        "checks": checks,
        "deployment_declared": False,
        "production_deployment": "NEVER_DECLARED",
        "next_action": _SUCCESS_ACTION if approved else _BLOCKED_ACTION % code,
        "evaluated_at": now.isoformat(),
    }


def evaluate_release(*, manifest, receipts, workspace, tests, auditor, reviewer,
                     key: bytes, now: datetime | None = None) -> dict:
    """Evaluate a caller-provided release package.  Never deploys anything.

    Returns a result dict with ``approved_for_staging`` (recommendation
    only), a stable ``reason`` code with ``reason_text``, the per-check
    ledger and an explicit ``production_deployment`` field that is always
    ``NEVER_DECLARED``.  Evidence problems are reported, never raised;
    programmer errors (naive clock, wrong key length) raise ValueError.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware 'now' required")
    _key(key)

    checks: list = []

    def fail(code: str, check: str, detail: str) -> dict:
        checks.append({"check": check, "status": "FAIL", "reason": code, "detail": detail})
        return _finalize(False, code, detail, checks, now)

    def passed(check: str, detail: str = "") -> None:
        checks.append({"check": check, "status": "PASS", "reason": REASON_OK, "detail": detail})

    # -------------------------------------------------- phase A: presence
    if not isinstance(manifest, dict):
        return fail(REASON_MISSING_EVIDENCE, "manifest", "release manifest was not provided")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        return fail(REASON_UNSUPPORTED_SCHEMA, "manifest", "unsupported manifest schema")
    for field in ("change_id", "target_environment", "agent", "source_files",
                  "diff", "required_reviewer"):
        if field not in manifest or manifest[field] is None:
            return fail(REASON_MISSING_EVIDENCE, "manifest",
                        "manifest field %r is absent" % field)
    if not isinstance(manifest["change_id"], str) or not manifest["change_id"].strip():
        return fail(REASON_MISSING_EVIDENCE, "manifest", "change_id is empty")
    if (not isinstance(manifest["required_reviewer"], str)
            or not manifest["required_reviewer"].strip()):
        return fail(REASON_MISSING_EVIDENCE, "manifest", "required_reviewer is empty")

    if not isinstance(receipts, (list, tuple)) or len(receipts) == 0:
        return fail(REASON_MISSING_EVIDENCE, "receipts", "no signed session receipts provided")

    if not isinstance(workspace, dict):
        return fail(REASON_MISSING_EVIDENCE, "workspace", "workspace fingerprint was not provided")
    if workspace.get("schema") != WORKSPACE_SCHEMA:
        return fail(REASON_UNSUPPORTED_SCHEMA, "workspace", "unsupported workspace schema")

    if not isinstance(tests, dict):
        return fail(REASON_MISSING_EVIDENCE, "test_evidence", "TEST evidence was not provided")
    if tests.get("schema") != TEST_EVIDENCE_SCHEMA:
        return fail(REASON_UNSUPPORTED_SCHEMA, "test_evidence", "unsupported test evidence schema")

    if not isinstance(auditor, dict):
        return fail(REASON_MISSING_EVIDENCE, "auditor", "auditor verdict was not provided")
    if auditor.get("schema") != AUDITOR_SCHEMA:
        return fail(REASON_UNSUPPORTED_SCHEMA, "auditor", "unsupported auditor schema")
    passed("evidence_presence", "manifest, receipts, workspace, test evidence, auditor")

    # --------------------------------------------------- phase B: ordering
    # 1. Production is never in scope for this gate.
    if manifest.get("production_approved"):
        return fail(REASON_PRODUCTION_APPROVED, "production_guard",
                    "manifest carries a production approval flag")
    target = manifest["target_environment"]
    if not isinstance(target, str):
        return fail(REASON_MISSING_EVIDENCE, "production_guard",
                    "target_environment is malformed")
    lowered = target.strip().lower()
    if lowered in {"production", "prod"}:
        return fail(REASON_PRODUCTION_APPROVED, "production_guard",
                    "release targets production")
    if lowered != "staging":
        return fail(REASON_UNSUPPORTED_TARGET, "production_guard",
                    "unsupported target %r" % target)
    passed("production_guard", "target=staging, no production approval")

    # 2. The producing agent must be terminal.
    agent = manifest["agent"]
    if not isinstance(agent, dict) or "id" not in agent or "state" not in agent:
        return fail(REASON_MISSING_EVIDENCE, "agent_terminality", "manifest.agent is incomplete")
    agent_id = agent["id"]
    if not isinstance(agent_id, str) or not agent_id.strip():
        return fail(REASON_MISSING_EVIDENCE, "agent_terminality", "agent id is empty")
    if agent["state"] != "complete":
        return fail(REASON_AGENT_INFLIGHT, "agent_terminality",
                    "agent state is %r, not terminal" % (agent["state"],))
    passed("agent_terminality", agent_id)

    # 3. Immutable Git workspace fingerprint must recompute locally.
    for field in ("commit", "tree", "dirty", "files", "fingerprint"):
        if field not in workspace or workspace[field] is None:
            return fail(REASON_MISSING_EVIDENCE, "workspace_fingerprint",
                        "workspace field %r is absent" % field)
    if workspace["dirty"] is not False:
        return fail(REASON_WORKSPACE_NOT_IMMUTABLE, "workspace_fingerprint",
                    "workspace is dirty or its state flag is unverifiable")
    commit, tree = workspace["commit"], workspace["tree"]
    if not isinstance(commit, str) or not HEX_ID.fullmatch(commit):
        return fail(REASON_WORKSPACE_NOT_IMMUTABLE, "workspace_fingerprint",
                    "commit id is not an immutable hex identifier")
    if not isinstance(tree, str) or not HEX_ID.fullmatch(tree):
        return fail(REASON_WORKSPACE_NOT_IMMUTABLE, "workspace_fingerprint",
                    "tree id is not an immutable hex identifier")
    snapshot = workspace["files"]
    if not isinstance(snapshot, list) or not snapshot:
        return fail(REASON_WORKSPACE_NOT_IMMUTABLE, "workspace_fingerprint",
                    "workspace file snapshot is empty")
    for entry in snapshot:
        if not _is_file_entry(entry):
            return fail(REASON_WORKSPACE_NOT_IMMUTABLE, "workspace_fingerprint",
                        "workspace file entry is malformed")
    fingerprint = compute_workspace_fingerprint(commit=commit, tree=tree, files=snapshot)
    declared_fp = workspace["fingerprint"]
    if not isinstance(declared_fp, str) or not hmac.compare_digest(fingerprint, declared_fp):
        return fail(REASON_WORKSPACE_FINGERPRINT_MISMATCH, "workspace_fingerprint",
                    "declared fingerprint does not match the recomputed snapshot")
    passed("workspace_fingerprint", fingerprint)

    # 4. Manifest source hashes must match the workspace snapshot.
    manifest_files = manifest["source_files"]
    if not isinstance(manifest_files, list) or not manifest_files:
        return fail(REASON_MISSING_EVIDENCE, "source_hashes", "no source files declared")
    declared: dict = {}
    for entry in manifest_files:
        if not _is_file_entry(entry):
            return fail(REASON_SOURCE_HASH_MISMATCH, "source_hashes",
                        "malformed source hash entry")
        declared[entry["path"]] = entry["sha256"]
    actual = {entry["path"]: entry["sha256"] for entry in snapshot}
    if set(declared) != set(actual):
        return fail(REASON_SOURCE_HASH_MISMATCH, "source_hashes",
                    "declared and workspace path sets differ")
    for path in sorted(declared):
        if declared[path] != actual[path]:
            return fail(REASON_SOURCE_HASH_MISMATCH, "source_hashes",
                        "hash mismatch for %s" % path)
    passed("source_hashes", "%d file(s) verified" % len(declared))

    # 5. A real diff must exist.
    diff = manifest["diff"]
    if not isinstance(diff, dict) or "patch" not in diff or "changed_paths" not in diff:
        return fail(REASON_MISSING_EVIDENCE, "diff", "diff evidence is incomplete")
    patch, changed_paths = diff["patch"], diff["changed_paths"]
    if not isinstance(patch, str) or not patch.strip():
        return fail(REASON_NO_DIFF, "diff", "patch text is empty")
    if (not isinstance(changed_paths, list) or not changed_paths
            or any(not isinstance(p, str) or not p.strip() for p in changed_paths)):
        return fail(REASON_NO_DIFF, "diff", "no changed paths declared")
    passed("diff", "%d changed path(s)" % len(changed_paths))

    # 6. Every receipt must verify, be in-window, terminal and bound here.
    for index, receipt in enumerate(receipts):
        label = "receipt[%d]" % index
        if not isinstance(receipt, dict):
            return fail(REASON_MISSING_EVIDENCE, label, "receipt is not an object")
        if receipt.get("schema") != RECEIPT_SCHEMA:
            return fail(REASON_UNSUPPORTED_SCHEMA, label, "unsupported receipt schema")
        body = {k: v for k, v in receipt.items() if k != "signature"}
        if set(body) != RECEIPT_BODY_FIELDS:
            return fail(REASON_RECEIPT_SIGNATURE_INVALID, label, "unexpected receipt fields")
        signature = receipt.get("signature")
        if not isinstance(signature, str) or not HEX64.fullmatch(signature):
            return fail(REASON_RECEIPT_SIGNATURE_INVALID, label,
                        "receipt is unsigned or the signature is malformed")
        if not isinstance(body["nonce"], str) or not NONCE.fullmatch(body["nonce"]):
            return fail(REASON_RECEIPT_SIGNATURE_INVALID, label, "invalid receipt nonce")
        desired = hmac.new(key, compact(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, desired):
            return fail(REASON_RECEIPT_SIGNATURE_INVALID, label,
                        "HMAC mismatch; receipt content was altered")
        if body["workspace_fingerprint"] != fingerprint:
            return fail(REASON_RECEIPT_FINGERPRINT_MISMATCH, label,
                        "receipt is bound to another workspace fingerprint")
        try:
            issued = datetime.fromisoformat(body["issued_at"])
            expires = datetime.fromisoformat(body["expires_at"])
        except (TypeError, ValueError):
            return fail(REASON_RECEIPT_TIME_INVALID, label, "receipt timestamps are malformed")
        if issued.tzinfo is None or issued.utcoffset() is None:
            return fail(REASON_RECEIPT_TIME_INVALID, label, "receipt issued_at is naive")
        if expires.tzinfo is None or expires.utcoffset() is None:
            return fail(REASON_RECEIPT_TIME_INVALID, label, "receipt expires_at is naive")
        if issued > now:
            return fail(REASON_RECEIPT_TIME_INVALID, label, "receipt issued in the future")
        if now > expires:
            return fail(REASON_RECEIPT_EXPIRED, label,
                        "receipt expired at %s" % body["expires_at"])
        if body["session_state"] != "complete":
            return fail(REASON_AGENT_INFLIGHT, label,
                        "session state is %r, not terminal" % (body["session_state"],))
        if body["agent"] != agent_id:
            return fail(REASON_RECEIPT_AGENT_MISMATCH, label,
                        "receipt issued to %r, manifest agent is %r"
                        % (body["agent"], agent_id))
        cost_error = _cost_error(body["cost"])
        if cost_error:
            return fail(REASON_UNKNOWN_COST, label, cost_error)
        passed(label, "session %s cost-terminal" % body["session_id"])

    # 7. TEST evidence must be GREEN for this exact snapshot.
    for field in ("framework", "command", "result", "cases_total", "cases_passed",
                  "failures", "errors", "ran_at", "workspace_fingerprint"):
        if field not in tests or tests[field] is None:
            return fail(REASON_MISSING_EVIDENCE, "test_evidence",
                        "test field %r is absent" % field)
    if tests["workspace_fingerprint"] != fingerprint:
        return fail(REASON_EVIDENCE_FINGERPRINT_MISMATCH, "test_evidence",
                    "evidence is bound to another workspace fingerprint")
    if tests["result"] != "GREEN":
        return fail(REASON_TESTS_RED, "test_evidence",
                    "test result is %r" % (tests["result"],))
    total, green, failures, errors = (tests["cases_total"], tests["cases_passed"],
                                      tests["failures"], tests["errors"])
    if type(total) is not int or total <= 0:
        return fail(REASON_TESTS_RED, "test_evidence", "no test cases were executed")
    if type(green) is not int or green != total:
        return fail(REASON_TESTS_RED, "test_evidence",
                    "test cases passed %r of %r" % (green, total))
    if type(failures) is not int or type(errors) is not int:
        return fail(REASON_MISSING_EVIDENCE, "test_evidence", "malformed failure counters")
    if failures or errors:
        return fail(REASON_TESTS_RED, "test_evidence",
                    "%d failure(s), %d error(s)" % (failures, errors))
    passed("test_evidence", "%d/%d GREEN" % (green, total))

    # 8. Independent auditor verdict, bound to this snapshot.
    for field in ("auditor", "verdict", "target_environment",
                  "audited_fingerprint", "issued_at"):
        if field not in auditor or auditor[field] is None:
            return fail(REASON_MISSING_EVIDENCE, "auditor",
                        "auditor field %r is absent" % field)
    auditor_id = auditor["auditor"]
    if not isinstance(auditor_id, str) or not auditor_id.strip():
        return fail(REASON_MISSING_EVIDENCE, "auditor", "auditor identity is empty")
    auditor_target = str(auditor["target_environment"]).strip().lower()
    if auditor_target in {"production", "prod"}:
        return fail(REASON_PRODUCTION_APPROVED, "auditor_verdict",
                    "auditor verdict covers production")
    if auditor_target != "staging":
        return fail(REASON_UNSUPPORTED_TARGET, "auditor_verdict",
                    "unsupported auditor target %r" % auditor["target_environment"])
    if auditor["verdict"] != "APPROVE_STAGING":
        return fail(REASON_AUDITOR_REJECTED, "auditor_verdict",
                    "verdict is %r" % (auditor["verdict"],))
    if auditor["audited_fingerprint"] != fingerprint:
        return fail(REASON_AUDITOR_FINGERPRINT_MISMATCH, "auditor_verdict",
                    "verdict is bound to another workspace fingerprint")
    if auditor_id == agent_id:
        return fail(REASON_AUDITOR_NOT_INDEPENDENT, "auditor_verdict",
                    "auditor reviewed its own change")
    passed("auditor_verdict", auditor_id)

    # 9. An independent, matching human reviewer.
    if not isinstance(reviewer, str) or not reviewer.strip():
        return fail(REASON_NO_REVIEWER, "reviewer", "no reviewer identity provided")
    if reviewer == agent_id or reviewer == auditor_id:
        return fail(REASON_REVIEWER_NOT_INDEPENDENT, "reviewer",
                    "reviewer must be independent of agent and auditor")
    if reviewer != manifest["required_reviewer"]:
        return fail(REASON_REVIEWER_MISMATCH, "reviewer",
                    "reviewer %r does not match required reviewer %r"
                    % (reviewer, manifest["required_reviewer"]))
    passed("reviewer", reviewer)

    return _finalize(True, REASON_OK,
                     "All staging checks passed; recommendation only, "
                     "no deployment was performed.",
                     checks, now)


__all__ = [
    "MANIFEST_SCHEMA", "RECEIPT_SCHEMA", "WORKSPACE_SCHEMA", "TEST_EVIDENCE_SCHEMA",
    "AUDITOR_SCHEMA", "RESULT_SCHEMA", "REASON_TEXT", "REASON_OK",
    "REASON_MISSING_EVIDENCE", "REASON_UNSUPPORTED_SCHEMA", "REASON_UNSUPPORTED_TARGET",
    "REASON_PRODUCTION_APPROVED", "REASON_WORKSPACE_NOT_IMMUTABLE",
    "REASON_WORKSPACE_FINGERPRINT_MISMATCH", "REASON_SOURCE_HASH_MISMATCH",
    "REASON_NO_DIFF", "REASON_RECEIPT_SIGNATURE_INVALID", "REASON_RECEIPT_TIME_INVALID",
    "REASON_RECEIPT_EXPIRED", "REASON_RECEIPT_FINGERPRINT_MISMATCH",
    "REASON_RECEIPT_AGENT_MISMATCH", "REASON_AGENT_INFLIGHT", "REASON_UNKNOWN_COST",
    "REASON_TESTS_RED", "REASON_EVIDENCE_FINGERPRINT_MISMATCH",
    "REASON_AUDITOR_FINGERPRINT_MISMATCH", "REASON_AUDITOR_REJECTED",
    "REASON_AUDITOR_NOT_INDEPENDENT", "REASON_NO_REVIEWER", "REASON_REVIEWER_MISMATCH",
    "REASON_REVIEWER_NOT_INDEPENDENT", "compact", "compute_workspace_fingerprint",
    "sign_session_receipt", "evaluate_release",
]
