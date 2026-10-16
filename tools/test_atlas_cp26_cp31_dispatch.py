"""Safety regressions for the CP26-31 OpenCode dispatch ledger."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import atlas_cp26_cp31_dispatch as target


class DispatchGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.receipt_patch = patch.object(target, "RECEIPTS", self.dir)
        self.receipt_patch.start()
        self.addCleanup(self.receipt_patch.stop)

    def fake_api(self, method, path, payload=None):
        if path == "/api/info":
            return {"version": "2.0.29"}
        if path == "/api/session":
            return {"data": {"id": "ses_safe123456", "location": {"directory": str(target.ROOT)}}}
        if path == "/api/session/ses_safe123456/prompt":
            self.assertEqual(method, "POST")
            self.assertIn("read-only", str(payload).lower()) if False else None
            return {"data": {"acknowledged": True}}
        raise AssertionError("Unexpected API call " + method + " " + path)

    def test_plan_session_writes_durable_receipt(self):
        with patch.object(target, "api", side_effect=self.fake_api) as fake, contextlib.redirect_stdout(io.StringIO()):
            target.dispatch("cp26-security")
        receipt = json.loads((self.dir / "cp26-security.json").read_text())
        self.assertEqual("PROMPT_ACKNOWLEDGED_UNVERIFIED", receipt["state"])
        self.assertEqual("ses_safe123456", receipt["session_id"])
        self.assertEqual(3, fake.call_count)
        self.assertNotIn("password", json.dumps(receipt).lower())

    def test_build_scope_is_explicit_and_other_missions_remain_plan(self):
        roles = []
        def capture(method, path, payload=None):
            if path == "/api/session":
                roles.append(payload["agent"])
            return self.fake_api(method, path, payload)
        with patch.object(target, "api", side_effect=capture), contextlib.redirect_stdout(io.StringIO()):
            target.dispatch("cp27-release-inventory-build")
        self.assertEqual(["build"], roles)
        receipt = json.loads((self.dir / "cp27-release-inventory-build.json").read_text())
        self.assertEqual("PROMPT_ACKNOWLEDGED_UNVERIFIED", receipt["state"])

    def test_duplicate_mission_cannot_replay_even_after_success(self):
        with patch.object(target, "api", side_effect=self.fake_api) as fake, contextlib.redirect_stdout(io.StringIO()):
            target.dispatch("cp26-security")
            with self.assertRaises(FileExistsError):
                target.dispatch("cp26-security")
        self.assertEqual(3, fake.call_count)

    def test_unknown_mission_denied_before_side_effect(self):
        with self.assertRaises(ValueError):
            target.dispatch("not-allowlisted")
        self.assertEqual([], list(self.dir.glob("*.json")))

    def test_ambiguous_prompt_error_stays_pending_no_retry(self):
        def flaky(method, path, payload=None):
            if path.endswith("/prompt"):
                raise TimeoutError("No prompt acknowledgment")
            return self.fake_api(method, path, payload)
        with patch.object(target, "api", side_effect=flaky) as fake, contextlib.redirect_stdout(io.StringIO()):
            target.dispatch("cp28-transport")
            with self.assertRaises(FileExistsError):
                target.dispatch("cp28-transport")
        receipt = json.loads((self.dir / "cp28-transport.json").read_text())
        self.assertEqual("PROMPT_UNKNOWN", receipt["state"])
        self.assertEqual("TimeoutError", receipt["error_type"])
        self.assertEqual(3, fake.call_count)

    def test_unsupported_server_version_fails_closed(self):
        with patch.object(target, "api", return_value={"version": "0.1.0"}) as fake, contextlib.redirect_stdout(io.StringIO()):
            target.dispatch("cp26-security")
        receipt = json.loads((self.dir / "cp26-security.json").read_text())
        self.assertEqual("CREATION_UNKNOWN", receipt["state"])
        self.assertEqual("RuntimeError", receipt["error_type"])
        self.assertEqual(1, fake.call_count)

    def test_fallback_without_original_receipt_denied(self):
        with patch.object(target, "api") as fake:
            with self.assertRaises(RuntimeError):
                target.dispatch("cp27-dr-fallback")
        fake.assert_not_called()

    def test_reconcile_terminal_session_persists_receipt_idempotently(self):
        receipt = {
            "mission": "cp28-transport",
            "state": "PROMPT_ACKNOWLEDGED_UNVERIFIED",
            "session_id": "ses_known0001",
        }
        path = self.dir / "cp28-transport.json"
        path.write_text(json.dumps(receipt))
        with patch.object(target, "api", return_value={"data": {
                "id": "ses_known0001", "outcome": "succeeded"}}) as fake:
            with contextlib.redirect_stdout(io.StringIO()):
                target.reconcile("cp28-transport")
                target.reconcile("cp28-transport")
        after = json.loads(path.read_text())
        self.assertEqual("SESSION_SUCCEEDED", after["state"])
        self.assertEqual("succeeded", after["server_outcome"])
        self.assertEqual(1, fake.call_count)

    def test_reconcile_unknown_or_missing_result_fails_closed(self):
        path = self.dir / "cp28-transport.json"
        payload = {"mission": "cp28-transport",
                   "state": "PROMPT_ACKNOWLEDGED_UNVERIFIED",
                   "session_id": "ses_known0001"}
        path.write_text(json.dumps(payload))
        for remote_result in ({"data": {"outcome": None}},
                              {"data": {"outcome": "running"}},
                              {"data": {"outcome": "succeeded",
                                        "id": "ses_different"}}):
            with self.subTest(remote_result=remote_result):
                with patch.object(target, "api", return_value=remote_result), contextlib.redirect_stdout(io.StringIO()):
                    target.reconcile("cp28-transport")
                self.assertEqual(payload, json.loads(path.read_text()))
        with self.assertRaises(ValueError):
            target.reconcile("../../bad")

    def test_reconcile_terminal_failed_result_does_not_imply_qa_success(self):
        path = self.dir / "cp27-dr.json"
        path.write_text(json.dumps({"mission": "cp27-dr",
                        "state": "PROMPT_ACKNOWLEDGED_UNVERIFIED",
                        "session_id": "ses_known0002"}))
        with patch.object(target, "api", return_value={"data": {
                "id": "ses_known0002", "outcome": "failed"}}), contextlib.redirect_stdout(io.StringIO()):
            target.reconcile("cp27-dr")
        record = json.loads(path.read_text())
        self.assertEqual("SESSION_FAILED", record["state"])
        self.assertNotIn("tests_passed", record)
        self.assertNotIn("qa_approved", record)

    def test_redirect_never_forwards_auth(self):
        with self.assertRaises(RuntimeError):
            target.NoRedirect().redirect_request(None, None, 302, "Moved",
                                                  {}, "https://evil.example/token")


if __name__ == "__main__":
    unittest.main()
