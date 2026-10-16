import json
import os
import unittest
from unittest.mock import Mock, patch

from infrastructure.pentium.atlas.agency_specialists import AgencyConfig, AgencyResult
from infrastructure.pentium.atlas.agency_worker_cli import run_once, MAX_REQUEST_BYTES


class CoreAgencyWorkerTests(unittest.TestCase):
    def cfg(self, enabled=True):
        return AgencyConfig(1, enabled, "core", "atlas-specialists", 2, 45, 8192, ("atlas",))
    def test_cannot_run_on_pentium(self):
        with self.assertRaisesRegex(ValueError, "core_worker_only"):
            run_once(b"{}", self.cfg(), Mock(), host="pentium")
    def test_disabled_by_default(self):
        with self.assertRaisesRegex(ValueError, "feature_disabled"):
            run_once(b"{}", self.cfg(False), Mock(), host="core")
    def test_reject_oversized_and_invalid_payload(self):
        with self.assertRaises(ValueError):
            run_once(b"x" * (MAX_REQUEST_BYTES + 1), self.cfg(), Mock(), host="core")
        with self.assertRaises(ValueError):
            run_once(b'{"objective":"test","inject":"reboot"}', self.cfg(), Mock(), host="core")
    def test_sends_read_only_typed_request(self):
        worker = Mock(return_value={"status": "succeeded", "summary": "ok", "agent_slugs": ["sre"]})
        req = {"task_id": "task-1", "project": "atlas", "objective": "Inspecionar logs",
               "risk": "READ", "specialists": ["sre"]}
        result = run_once(json.dumps(req).encode(), self.cfg(), worker, host="core")
        self.assertEqual("succeeded", result["status"])
        called = worker.call_args.args[0]
        self.assertEqual("READ", called.risk)
        self.assertEqual(("sre",), tuple(called.specialists))
    def test_refuses_unknown_project_and_control(self):
        worker = Mock()
        for values in (
            {"task_id": "t1", "project": "unlisted", "objective": "ok", "risk": "READ"},
            {"task_id": "t1", "project": "atlas", "objective": "ok", "risk": "CONTROL"},
        ):
            with self.assertRaises(ValueError):
                run_once(json.dumps(values).encode(), self.cfg(), worker, host="core")
        worker.assert_not_called()

    # --- Security Gap 1: staging env bypass on non-core host ---
    def test_staging_env_does_not_bypass_on_pentium(self):
        """ATLAS_CORE_STAGING_CONTAINER=1 must NOT allow execution when host='pentium'."""
        with patch.dict(os.environ, {"ATLAS_CORE_STAGING_CONTAINER": "1"}):
            with self.assertRaisesRegex(ValueError, "core_worker_only"):
                run_once(b"{}", self.cfg(), Mock(), host="pentium")

    def test_staging_env_allows_on_core_host(self):
        """ATLAS_CORE_STAGING_CONTAINER=1 SHOULD allow execution when host='core' (staging container)."""
        worker = Mock(return_value={"status": "succeeded", "summary": "ok", "agent_slugs": ["sre"]})
        with patch.dict(os.environ, {"ATLAS_CORE_STAGING_CONTAINER": "1"}):
            req = {"task_id": "task-1", "project": "atlas", "objective": "Inspecionar logs",
                   "risk": "READ", "specialists": ["sre"]}
            result = run_once(json.dumps(req).encode(), self.cfg(), worker, host="core")
            self.assertEqual("succeeded", result["status"])

    # --- Security Gap 2: validate strict AgencyResult contract ---
    def test_worker_result_with_extra_actions_field_raises(self):
        """Malicious worker response with 'actions' field must raise ValueError."""
        # Worker returns extra 'actions' field not in _RESULT_KEYS
        worker = Mock(return_value={
            "status": "succeeded",
            "summary": "ok",
            "actions": [{"type": "shell", "cmd": "rm -rf /"}]  # malicious extra field
        })
        req = {"task_id": "task-1", "project": "atlas", "objective": "Inspecionar logs",
               "risk": "READ", "specialists": ["sre"]}
        with self.assertRaisesRegex(ValueError, "result_schema_invalid"):
            run_once(json.dumps(req).encode(), self.cfg(), worker, host="core")

    def test_worker_result_with_invalid_status_raises(self):
        """Worker response with status != 'succeeded' must raise ValueError."""
        worker = Mock(return_value={"status": "failed", "summary": "error"})
        req = {"task_id": "task-1", "project": "atlas", "objective": "Inspecionar logs",
               "risk": "READ", "specialists": ["sre"]}
        with self.assertRaisesRegex(ValueError, "result_status_invalid"):
            run_once(json.dumps(req).encode(), self.cfg(), worker, host="core")

    def test_valid_worker_result_converted_to_strict_typed_fields(self):
        """Valid full worker result must be converted to minimal typed AgencyResult fields only."""
        worker = Mock(return_value={
            "status": "succeeded",
            "summary": "Assessment complete",
            "agent_slugs": ["sre", "security"],
            "evidence_refs": ["file1.log", "file2.log"],
            "tests_run": ["test_a", "test_b"],
            "limitations": ["no access to prod"],
            "proposed_changes": ["add monitoring", "review config"]
        })
        req = {"task_id": "task-1", "project": "atlas", "objective": "Inspecionar logs",
               "risk": "READ", "specialists": ["sre", "security"]}
        result = run_once(json.dumps(req).encode(), self.cfg(), worker, host="core")
        
        # Must contain ONLY the strict AgencyResult fields (no extra fields)
        expected_keys = {"status", "reason", "summary", "agent_slugs", "evidence_refs", 
                         "proposed_changes", "tests_run", "limitations"}
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["reason"], "")  # default
        self.assertEqual(result["summary"], "Assessment complete")
        self.assertEqual(result["agent_slugs"], ("sre", "security"))
        self.assertEqual(result["evidence_refs"], ("file1.log", "file2.log"))
        self.assertEqual(result["tests_run"], ("test_a", "test_b"))
        self.assertEqual(result["limitations"], ("no access to prod",))
        self.assertEqual(result["proposed_changes"], ("add monitoring", "review config"))
        
        # All tuple fields must be tuples (JSON serializable as arrays)
        for key in ("agent_slugs", "evidence_refs", "tests_run", "limitations", "proposed_changes"):
            self.assertIsInstance(result[key], tuple)

    def test_response_size_enforced_before_return(self):
        """Result exceeding config.max_response_bytes must raise ValueError."""
        # Create a valid result that when serialized exceeds max_response_bytes (8192).
        # Summary max is 4000, so use many evidence_refs and proposed_changes to push total size.
        worker = Mock(return_value={
            "status": "succeeded",
            "summary": "x" * 4000,  # max valid summary
            "agent_slugs": ["sre"],
            "evidence_refs": ["ref" + "x" * 200] * 16,  # 16 refs ~ 3.5KB
            "tests_run": ["test" + "x" * 200] * 16,     # 16 tests ~ 3.5KB
            "limitations": ["lim" + "x" * 200] * 12,    # 12 limitations ~ 2.5KB
            "proposed_changes": ["change" + "x" * 500] * 12,  # 12 changes ~ 6KB
        })
        req = {"task_id": "task-1", "project": "atlas", "objective": "Inspecionar logs",
               "risk": "READ", "specialists": ["sre"]}
        with self.assertRaisesRegex(ValueError, "result_too_large"):
            run_once(json.dumps(req).encode(), self.cfg(), worker, host="core")


if __name__ == "__main__":
    unittest.main()
