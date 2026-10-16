"""CP14 offline release gate TDD suite (additive, fail-closed).

Contract under test: cp14_release_gate.evaluate_release() accepts only
caller-provided manifests, HMAC-signed cost-terminal session receipts,
immutable Git workspace fingerprints, TEST evidence and an independent
auditor verdict.  Every absence or inconsistency blocks staging approval
with a human-readable reason code, and no code path declares deployment.
"""
from __future__ import annotations

import ast
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cp14_release_gate as gate

NOW = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
KEY = bytes(range(32))
REVIEWER = "atlas-cto"
AGENT_ID = "opencode/release-agent"
COMMIT = "a" * 40
TREE = "b" * 40


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_files() -> list:
    return [
        {"path": "cp14_release_gate.py", "sha256": _sha("cp14-module-body")},
        {"path": "test_cp14_release_gate.py", "sha256": _sha("cp14-test-body")},
    ]


def make_workspace(**over) -> dict:
    files = source_files()
    data = {
        "schema": gate.WORKSPACE_SCHEMA,
        "commit": COMMIT,
        "tree": TREE,
        "dirty": False,
        "files": files,
        "fingerprint": gate.compute_workspace_fingerprint(
            commit=COMMIT, tree=TREE, files=files),
    }
    data.update(over)
    return data


def make_manifest(**over) -> dict:
    data = {
        "schema": gate.MANIFEST_SCHEMA,
        "change_id": "CP-ORCH-14",
        "target_environment": "staging",
        "agent": {"id": AGENT_ID, "state": "complete"},
        "required_reviewer": REVIEWER,
        "source_files": source_files(),
        "diff": {
            "changed_paths": ["cp14_release_gate.py"],
            "patch": "diff --git a/cp14_release_gate.py b/cp14_release_gate.py\n+line\n",
        },
    }
    data.update(over)
    return data


def make_receipt(fingerprint: str, **over) -> dict:
    body = {
        "session_id": "sess-cp14",
        "agent": AGENT_ID,
        "workspace_fingerprint": fingerprint,
        "issued_at": NOW - timedelta(hours=1),
        "expires_at": NOW + timedelta(hours=6),
        "session_state": "complete",
        "cost": {"currency": "USD", "total_usd": 0.0,
                 "terminal": True, "basis": "free_tier"},
    }
    body.update(over)
    return gate.sign_session_receipt(key=KEY, **body)


def make_evidence(fingerprint: str, **over) -> dict:
    data = {
        "schema": gate.TEST_EVIDENCE_SCHEMA,
        "framework": "unittest",
        "command": "python -m unittest test_cp14_release_gate -v",
        "result": "GREEN",
        "cases_total": 42,
        "cases_passed": 42,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "ran_at": NOW.isoformat(),
        "workspace_fingerprint": fingerprint,
    }
    data.update(over)
    return data


def make_auditor(fingerprint: str, **over) -> dict:
    data = {
        "schema": gate.AUDITOR_SCHEMA,
        "auditor": "independent-auditor",
        "verdict": "APPROVE_STAGING",
        "target_environment": "staging",
        "audited_fingerprint": fingerprint,
        "issued_at": NOW.isoformat(),
    }
    data.update(over)
    return data


class ReleaseGateTests(unittest.TestCase):
    """Every test mutates exactly one property of an otherwise valid package."""

    def package(self) -> dict:
        ws = make_workspace()
        fp = ws["fingerprint"]
        return {
            "manifest": make_manifest(),
            "receipts": [make_receipt(fp)],
            "workspace": ws,
            "tests": make_evidence(fp),
            "auditor": make_auditor(fp),
            "reviewer": REVIEWER,
            "key": KEY,
            "now": NOW,
        }

    def evaluate(self, **overrides) -> dict:
        params = self.package()
        params.update(overrides)
        return gate.evaluate_release(**params)

    def assertBlocked(self, res: dict, code: str) -> None:
        self.assertIsInstance(res, dict)
        self.assertFalse(res["approved_for_staging"],
                         "must fail closed, got %r" % (res,))
        self.assertEqual(res["reason"], code)
        self.assertEqual(res["reason_text"], gate.REASON_TEXT[code])
        self.assertTrue(res["reason_text"].strip())
        self.assertEqual(res["checks"][-1]["status"], "FAIL")
        self.assertEqual(res["checks"][-1]["reason"], code)
        self.assertFalse(res["deployment_declared"])
        self.assertEqual(res["production_deployment"], "NEVER_DECLARED")

    # ---------------------------------------------------------------- happy
    def test_valid_package_is_approved_for_staging_only(self):
        res = self.evaluate()
        self.assertTrue(res["approved_for_staging"])
        self.assertEqual(res["reason"], gate.REASON_OK)
        self.assertEqual(res["reason_text"], gate.REASON_TEXT[gate.REASON_OK])
        self.assertFalse(res["deployment_declared"])
        self.assertEqual(res["production_deployment"], "NEVER_DECLARED")
        self.assertGreaterEqual(len(res["checks"]), 10)
        self.assertTrue(all(c["status"] == "PASS" for c in res["checks"]))

    def test_known_terminal_cost_is_not_treated_as_unknown(self):
        """Known, terminal, non-negative cost is data, not an unknown cost."""
        fp = self.package()["workspace"]["fingerprint"]
        res = self.evaluate(receipts=[make_receipt(
            fp, cost={"currency": "USD", "total_usd": 0.42,
                      "terminal": True, "basis": "metered"})])
        self.assertTrue(res["approved_for_staging"])
        self.assertEqual(res["reason"], gate.REASON_OK)

    def test_result_never_declares_production_deployment(self):
        for res in (self.evaluate(),
                    self.evaluate(manifest=make_manifest(production_approved=True))):
            payload = json.dumps(res, sort_keys=True).lower()
            self.assertNotIn("deployed", payload)
            self.assertIn('"deployment_declared": false', payload)
            self.assertIn('"production_deployment": "never_declared"', payload)

    def test_every_reason_code_has_human_readable_text(self):
        names = [n for n in dir(gate)
                 if n.startswith("REASON_") and n != "REASON_TEXT"]
        self.assertGreaterEqual(len(names), 12)
        for name in names:
            code = getattr(gate, name)
            self.assertIsInstance(code, str)
            self.assertRegex(code, r"^[A-Z][A-Z0-9_]*$")
            self.assertIn(code, gate.REASON_TEXT)
            self.assertTrue(gate.REASON_TEXT[code].strip())

    # ------------------------------------------------------ absent evidence
    def test_missing_manifest_fails_closed(self):
        self.assertBlocked(self.evaluate(manifest=None),
                           gate.REASON_MISSING_EVIDENCE)

    def test_missing_workspace_fails_closed(self):
        self.assertBlocked(self.evaluate(workspace=None),
                           gate.REASON_MISSING_EVIDENCE)

    def test_missing_receipts_fails_closed(self):
        self.assertBlocked(self.evaluate(receipts=[]),
                           gate.REASON_MISSING_EVIDENCE)
        self.assertBlocked(self.evaluate(receipts=None),
                           gate.REASON_MISSING_EVIDENCE)

    def test_missing_test_evidence_fails_closed(self):
        self.assertBlocked(self.evaluate(tests=None),
                           gate.REASON_MISSING_EVIDENCE)

    def test_missing_auditor_fails_closed(self):
        self.assertBlocked(self.evaluate(auditor=None),
                           gate.REASON_MISSING_EVIDENCE)

    def test_missing_diff_fails_closed(self):
        manifest = make_manifest()
        del manifest["diff"]
        self.assertBlocked(self.evaluate(manifest=manifest),
                           gate.REASON_MISSING_EVIDENCE)

    def test_unsigned_receipt_shape_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        forged = make_receipt(fp)
        del forged["signature"]
        self.assertBlocked(self.evaluate(receipts=[forged]),
                           gate.REASON_RECEIPT_SIGNATURE_INVALID)

    # -------------------------------------------------------- source / diff
    def test_source_hash_mismatch_fails_closed(self):
        files = source_files()
        files[0] = dict(files[0], sha256="0" * 64)
        self.assertBlocked(self.evaluate(manifest=make_manifest(source_files=files)),
                           gate.REASON_SOURCE_HASH_MISMATCH)

    def test_source_path_set_mismatch_fails_closed(self):
        files = source_files() + [{"path": "extra.py", "sha256": _sha("extra")}]
        self.assertBlocked(self.evaluate(manifest=make_manifest(source_files=files)),
                           gate.REASON_SOURCE_HASH_MISMATCH)

    def test_empty_patch_fails_closed(self):
        diff = {"changed_paths": ["cp14_release_gate.py"], "patch": "   "}
        self.assertBlocked(self.evaluate(manifest=make_manifest(diff=diff)),
                           gate.REASON_NO_DIFF)

    def test_no_changed_paths_fails_closed(self):
        diff = {"changed_paths": [], "patch": "+line\n"}
        self.assertBlocked(self.evaluate(manifest=make_manifest(diff=diff)),
                           gate.REASON_NO_DIFF)

    # --------------------------------------------------------------- tests
    def test_red_tests_fails_closed(self):
        evidence = make_evidence(
            self.package()["workspace"]["fingerprint"],
            result="RED", cases_total=42, cases_passed=40, failures=2, errors=0)
        self.assertBlocked(self.evaluate(tests=evidence), gate.REASON_TESTS_RED)

    def test_incomplete_test_run_fails_closed(self):
        evidence = make_evidence(
            self.package()["workspace"]["fingerprint"],
            cases_total=42, cases_passed=41, failures=1, errors=0)
        self.assertBlocked(self.evaluate(tests=evidence), gate.REASON_TESTS_RED)

    def test_zero_executed_tests_fail_closed(self):
        evidence = make_evidence(
            self.package()["workspace"]["fingerprint"],
            cases_total=0, cases_passed=0)
        self.assertBlocked(self.evaluate(tests=evidence), gate.REASON_TESTS_RED)

    def test_test_evidence_bound_to_other_workspace_fails_closed(self):
        evidence = make_evidence("f" * 64)
        self.assertBlocked(self.evaluate(tests=evidence),
                           gate.REASON_EVIDENCE_FINGERPRINT_MISMATCH)

    # --------------------------------------------------------------- agent
    def test_manifest_agent_inflight_fails_closed(self):
        manifest = make_manifest(agent={"id": AGENT_ID, "state": "inflight"})
        self.assertBlocked(self.evaluate(manifest=manifest),
                           gate.REASON_AGENT_INFLIGHT)

    def test_receipt_agent_inflight_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        self.assertBlocked(
            self.evaluate(receipts=[make_receipt(fp, session_state="inflight")]),
            gate.REASON_AGENT_INFLIGHT)

    # --------------------------------------------------------------- costs
    def test_cost_without_terminal_flag_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        cost = {"currency": "USD", "total_usd": 0.0, "terminal": False}
        self.assertBlocked(self.evaluate(receipts=[make_receipt(fp, cost=cost)]),
                           gate.REASON_UNKNOWN_COST)

    def test_non_numeric_cost_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        cost = {"currency": "USD", "total_usd": "n/a", "terminal": True}
        self.assertBlocked(self.evaluate(receipts=[make_receipt(fp, cost=cost)]),
                           gate.REASON_UNKNOWN_COST)

    def test_unknown_currency_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        cost = {"currency": "BTC", "total_usd": 1, "terminal": True}
        self.assertBlocked(self.evaluate(receipts=[make_receipt(fp, cost=cost)]),
                           gate.REASON_UNKNOWN_COST)

    # ------------------------------------------------------------ receipts
    def test_expired_receipt_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        expired = make_receipt(fp, issued_at=NOW - timedelta(hours=9),
                               expires_at=NOW - timedelta(minutes=1))
        self.assertBlocked(self.evaluate(receipts=[expired]),
                           gate.REASON_RECEIPT_EXPIRED)

    def test_future_issued_receipt_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        future = make_receipt(fp, issued_at=NOW + timedelta(hours=1),
                              expires_at=NOW + timedelta(hours=6))
        self.assertBlocked(self.evaluate(receipts=[future]),
                           gate.REASON_RECEIPT_TIME_INVALID)

    def test_tampered_receipt_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        tampered = dict(make_receipt(fp), session_state="inflight")
        self.assertBlocked(self.evaluate(receipts=[tampered]),
                           gate.REASON_RECEIPT_SIGNATURE_INVALID)

    def test_receipt_for_other_workspace_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        other = make_receipt("f" * 64)
        self.assertBlocked(self.evaluate(receipts=[other]),
                           gate.REASON_RECEIPT_FINGERPRINT_MISMATCH)

    def test_receipt_from_other_agent_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        other = make_receipt(fp, agent="other/agent")
        self.assertBlocked(self.evaluate(receipts=[other]),
                           gate.REASON_RECEIPT_AGENT_MISMATCH)

    # ----------------------------------------------------------- workspace
    def test_dirty_workspace_fails_closed(self):
        self.assertBlocked(self.evaluate(workspace=make_workspace(dirty=True)),
                           gate.REASON_WORKSPACE_NOT_IMMUTABLE)

    def test_tampered_workspace_fingerprint_fails_closed(self):
        self.assertBlocked(
            self.evaluate(workspace=make_workspace(fingerprint="c" * 64)),
            gate.REASON_WORKSPACE_FINGERPRINT_MISMATCH)

    def test_workspace_with_non_hex_head_fails_closed(self):
        self.assertBlocked(self.evaluate(workspace=make_workspace(commit="HEAD!")),
                           gate.REASON_WORKSPACE_NOT_IMMUTABLE)

    # ------------------------------------------------------------- auditor
    def test_rejected_auditor_verdict_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        self.assertBlocked(self.evaluate(auditor=make_auditor(fp, verdict="REJECT")),
                           gate.REASON_AUDITOR_REJECTED)

    def test_auditor_bound_to_other_workspace_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        self.assertBlocked(
            self.evaluate(auditor=make_auditor(fp, audited_fingerprint="e" * 64)),
            gate.REASON_AUDITOR_FINGERPRINT_MISMATCH)

    def test_self_auditor_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        self.assertBlocked(self.evaluate(auditor=make_auditor(fp, auditor=AGENT_ID)),
                           gate.REASON_AUDITOR_NOT_INDEPENDENT)

    def test_production_auditor_verdict_fails_closed(self):
        fp = self.package()["workspace"]["fingerprint"]
        self.assertBlocked(
            self.evaluate(auditor=make_auditor(fp, target_environment="production")),
            gate.REASON_PRODUCTION_APPROVED)

    # ------------------------------------------------------------- reviewer
    def test_missing_reviewer_fails_closed(self):
        self.assertBlocked(self.evaluate(reviewer=""), gate.REASON_NO_REVIEWER)
        self.assertBlocked(self.evaluate(reviewer=None), gate.REASON_NO_REVIEWER)

    def test_mismatched_reviewer_fails_closed(self):
        self.assertBlocked(self.evaluate(reviewer="random-approver"),
                           gate.REASON_REVIEWER_MISMATCH)

    def test_self_review_fails_closed(self):
        self.assertBlocked(self.evaluate(reviewer=AGENT_ID),
                           gate.REASON_REVIEWER_NOT_INDEPENDENT)
        fp = self.package()["workspace"]["fingerprint"]
        self.assertBlocked(self.evaluate(reviewer="independent-auditor"),
                           gate.REASON_REVIEWER_NOT_INDEPENDENT)

    # ----------------------------------------------------------- production
    def test_production_approved_flag_fails_closed(self):
        self.assertBlocked(
            self.evaluate(manifest=make_manifest(production_approved=True)),
            gate.REASON_PRODUCTION_APPROVED)

    def test_production_target_environment_fails_closed(self):
        self.assertBlocked(
            self.evaluate(manifest=make_manifest(target_environment="production")),
            gate.REASON_PRODUCTION_APPROVED)

    def test_unsupported_target_environment_fails_closed(self):
        self.assertBlocked(
            self.evaluate(manifest=make_manifest(target_environment="qa")),
            gate.REASON_UNSUPPORTED_TARGET)

    # -------------------------------------------------------------- hygiene
    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate(now=datetime(2026, 10, 14, 18, 0, 0))

    def test_wrong_key_length_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate(key=b"short")

    def test_runtime_module_avoids_os_commands_and_credentials(self):
        """The runtime module must stay offline: no OS commands, no file IO,
        no network, no credential material."""
        allowed_imports = {"__future__", "datetime", "hashlib", "hmac",
                           "json", "re", "typing"}
        banned_calls = {"system", "popen", "Popen", "run", "check_output",
                        "check_call", "urlopen", "execv", "spawn",
                        "read_text", "write_text", "read_bytes", "write_bytes"}
        banned_tokens = ("os.system", "subprocess", "api_key", "password=",
                         "BEGIN RSA", "Bearer ", "socket", "urllib")
        source = Path(gate.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertLessEqual(imported, allowed_imports,
                             "unexpected imports: %r" % (imported - allowed_imports))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    called.add(func.attr)
                elif isinstance(func, ast.Name):
                    called.add(func.id)
        self.assertFalse(called & banned_calls,
                         "banned call surface: %r" % (called & banned_calls))
        for token in banned_tokens:
            self.assertNotIn(token, source, "banned token %r" % token)


if __name__ == "__main__":
    unittest.main()
