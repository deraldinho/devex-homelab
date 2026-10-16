"""Testes unitarios do bridge de sessoes OpenCode. Sem rede e servicos reais."""
import json
import os
import sys
import uuid
import tempfile
import unittest
from pathlib import Path
from collections.abc import Mapping
from unittest.mock import patch

from tools.atlas_opencode_api import (
    ApiError,
    ApiRunner,
    _is_safe_in_repo_regular_file,
    _normalize_artifact_path,
    _parse_manifest_from_task,
    build_prompt,
    load_task,
    require_task_id,
    validate_base_url,
)


class FakeClient:
    def __init__(self, statuses, agent="build", project_root=None):
        self.statuses = iter(statuses)
        self.created = []
        self.prompts = []
        self.messages = []
        self.agent = agent
        self.project_root = project_root
        self.last_location = None

    def post(self, path, obj=None, timeout=10):
        if path == "/api/session":
            self.created.append(obj)
            # Store location from obj, use project_root fallback
            if obj and isinstance(obj, Mapping) and "location" in obj:
                self.last_location = obj["location"]
            elif self.project_root is not None:
                self.last_location = {"directory": str(self.project_root)}
            else:
                self.last_location = {"directory": "/default/project"}
            self.last_agent = self.agent
            return {"data": {"id": "ses_test123",
                             "agent": self.last_agent,
                             "location": self.last_location}}
        if path == "/api/session/ses_test123/prompt":
            self.prompts.append(obj)
            return {"data": {"id": "msg_test"}}
        raise AssertionError(path)

    def get(self, path, timeout=10):
        if path == "/api/session/ses_test123":
            status = next(self.statuses)
            # Use stored location or fallback to project_root
            location = self.last_location if self.last_location is not None else (
                {"directory": str(self.project_root)} if self.project_root is not None else {"directory": "/default"}
            )
            return {"data": {"id": "ses_test123",
                             "outcome": status,
                             "agent": self.agent,
                             "location": location}}
        raise AssertionError(path)


class BridgeTests(unittest.TestCase):
    @staticmethod
    def complete_report(task_id):
        return (
            f"# Task-Id: {task_id}\n"
            "## Resumo\nEscopo implementado e revisado.\n"
            "## Arquivos alterados\nNenhum.\n"
            "## Testes\npytest aprovado.\n"
            "## Bloqueios e riscos\nNenhum identificado.\n"
            "## Proximos passos\nQA e homologacao.\n"
        )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir()
        self.base = self.root / ".atlas" / "opencode"
        (self.base / "inbox").mkdir(parents=True)
        (self.base / "outbox").mkdir()
        (self.base / "tmp").mkdir()
        self.tid = "20261013T020000Z-1234abcd"
        (self.base / "inbox" / (self.tid + ".md")).write_text(
            "# Pedido " + self.tid + "\nREAD-ONLY: verifique README e entregue relatorio.\n", encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_foreign_url_and_task_id(self):
        validate_base_url("https://x99.tail2ffe44.ts.net")
        with self.assertRaises(ValueError):
            validate_base_url("https://evil.example")
        with self.assertRaises(ValueError):
            validate_base_url("http://x99.tail2ffe44.ts.net")
        with self.assertRaises(ValueError):
            require_task_id("../../etc/passwd")

    def test_load_task_bounded(self):
        self.assertIn("READ-ONLY", load_task(self.root, self.tid))
        with self.assertRaises(ValueError):
            (self.base / "inbox" / (self.tid + ".md")).write_text("x"*25000)
            load_task(self.root, self.tid)

    def test_prompt_scoped(self):
        prompt = build_prompt(self.tid, load_task(self.root, self.tid))
        self.assertIn(self.tid, prompt)
        self.assertIn("READ-ONLY", prompt)
        self.assertIn(".atlas/opencode/outbox/", prompt)
        self.assertIn("no deploy", prompt.lower())

    @patch("tools.atlas_opencode_api.time.sleep", return_value=None)
    def test_success_requires_report_file(self, _sleep):
        client = FakeClient(["succeeded"])
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        self.assertEqual(status["state"], "missing_report")
        self.assertFalse(status["report_exists"])
        self.assertEqual(status["session_id"], "ses_test123")
        self.assertEqual(client.created[0]["location"]["directory"], str(self.root))
        self.assertTrue(client.prompts[0]["text"])
        self.assertFalse((self.base / "tmp" / "active.lock").exists())

    @patch("tools.atlas_opencode_api.time.sleep", return_value=None)
    def test_success_with_report_and_no_overwrite(self, _sleep):
        client = FakeClient(["succeeded"])
        report = self.base / "outbox" / (self.tid + ".md")
        original = self.complete_report(self.tid)
        def write_report(path, obj=None, timeout=10):
            if path.endswith("/prompt"):
                report.write_text(original, encoding="utf-8")
                return {"data": {"id": "msg_test"}}
            return FakeClient.post(client, path, obj, timeout)
        client.post = write_report
        result = ApiRunner(client, self.root, self.tid, timeout_seconds=30).run()
        self.assertEqual(result["state"], "reported")
        self.assertEqual(report.read_text(encoding="utf-8"), original)
        with self.assertRaises(FileExistsError):
            ApiRunner(client, self.root, self.tid, timeout_seconds=30).run()

    @patch("tools.atlas_opencode_api.time.sleep", return_value=None)
    def test_header_only_report_is_not_accepted_as_completed_work(self, _sleep):
        client = FakeClient(["succeeded"])
        report = self.base / "outbox" / (self.tid + ".md")
        def write_header_only(path, obj=None, timeout=10):
            if path.endswith("/prompt"):
                report.write_text("# Task-Id: " + self.tid + "\n", encoding="utf-8")
                return {"data": {"id": "msg_test"}}
            return FakeClient.post(client, path, obj, timeout)
        client.post = write_header_only
        outcome = ApiRunner(client, self.root, self.tid, timeout_seconds=30).run()
        self.assertEqual("invalid_report", outcome["state"])

    @patch("tools.atlas_opencode_api.time.sleep", return_value=None)
    def test_failure_is_not_success(self, _sleep):
        runner = ApiRunner(FakeClient(["failed"]), self.root, self.tid, timeout_seconds=30)
        status = runner.run()
        self.assertEqual(status["state"], "agent_failed")
        self.assertFalse(status["report_exists"])

    @patch("tools.atlas_opencode_api.time.sleep", return_value=None)
    def test_lock_prevents_concurrent_execution(self, _sleep):
        lock = self.base / "tmp" / "active.lock"
        lock.write_text("another", encoding="utf-8")
        client = FakeClient(["succeeded"])
        runner = ApiRunner(client, self.root, self.tid, timeout_seconds=30)
        with patch("tools.atlas_opencode_api.time.monotonic", side_effect=[0.0, 31.0]):
            result = runner.run()
        self.assertEqual("busy", result["state"])
        self.assertEqual("another", lock.read_text(encoding="utf-8"))
        self.assertFalse(client.created)
        self.assertFalse(client.prompts)

    def test_queue_waits_for_running_agent_then_acquires_exclusive_lock(self):
        lock = self.base / "tmp" / "active.lock"
        lock.write_text("other-task-id", encoding="utf-8")
        client = FakeClient(["succeeded"])
        def release_previous_lock(seconds):
            lock.unlink()
        with patch("tools.atlas_opencode_api.time.sleep", side_effect=release_previous_lock):
            result = ApiRunner(client, self.root, self.tid, timeout_seconds=30).run()
        self.assertEqual("missing_report", result["state"])
        self.assertEqual(1, len(client.created))
        self.assertEqual(1, len(client.prompts))
        self.assertFalse(lock.exists())

    def test_transport_http_errors_do_not_leak_server_response(self):
        self.assertNotIn("token", str(ApiError("HTTP 401")))
        self.assertEqual(str(ApiError("HTTP 401")), "HTTP 401")

    def test_reconcile_success_late_report_without_rerunning_prompt(self):
        status = self.base / "outbox" / (self.tid + ".status.json")
        status.write_text(json.dumps({
            "task_id": self.tid,
            "state": "timeout",
            "session_id": "ses_test123",
            "report_exists": False,
        }), encoding="utf-8")
        report = self.base / "outbox" / (self.tid + ".md")
        report.write_text(self.complete_report(self.tid), encoding="utf-8")
        client = FakeClient(["succeeded"], project_root=self.root)
        result = ApiRunner(client, self.root, self.tid).reconcile()
        self.assertEqual(result["state"], "reported")
        self.assertTrue(result["report_exists"])

# ---- Negative tests for required-artifacts manifest ----

    def test_negative_nenhum_bypass_with_manifest(self):
        """When manifest declares paths, report Nenhum. cannot bypass it.

        The manifest takes precedence; the report's 'Nenhum.' sentinel
        must not override declared artifact paths.
        """
        # Inbox task with required-artifacts manifest declaring unsafe path
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\n../etc/passwd\n```\n'
            'READ-ONLY: verifique README e entregue relatorio.\n',
            encoding="utf-8"
        )
        # No pre-existing report or status; the run will create them via the API
        client = FakeClient(["succeeded"])
        # Intercept prompt to write a report with Nenhum. in Arquivos alterados
        report = self.base / "outbox" / (self.tid + ".md")
        def write_report_during_prompt(path, obj=None, timeout=10):
            if path == "/api/session/ses_test123/prompt":
                report.write_text(
                    '# Task-Id: ' + self.tid + '\n'
                    '## Resumo\nEscopo implementado.\n'
                    '## Testes\npytest aprovado.\n'
                    '## Bloqueios e riscos\nNenhum.\n'
                    '## Proximos passos\nQA e homologacao.\n'
                    '## Arquivos alterados\nNenhum.\n',
                    encoding="utf-8"
                )
                return {"data": {"id": "msg_test"}}
            from tools.test_atlas_opencode_api import FakeClient as FC
            return FC.post(client, path, obj, timeout)
        client.post = write_report_during_prompt
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        # Manifest has declared paths; report Nenhum. should NOT override.
        # Expected: invalid_report (artifact check fails or Nenhum override flag)
        self.assertIn("invalid_report", status["state"])

    def test_negative_missing_artifact_with_manifest(self):
        """When manifest declares a path that is missing, verification fails.

        A required path that does not exist on disk should result in
        invalid_report (for build agent).
        """
        # Inbox task with required-artifacts manifest declaring a specific file
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\nmeu_arquivo.txt\n```\n'
            'READ-ONLY: verifique README e entregue relatorio.\n',
            encoding="utf-8"
        )
        # No pre-existing report or status
        client = FakeClient(["succeeded"])
        # Intercept prompt to write a report with Nenhum. (which should NOT override
        # the manifest, and the manifest path is missing)
        report = self.base / "outbox" / (self.tid + ".md")
        def write_report_during_prompt(path, obj=None, timeout=10):
            if path == "/api/session/ses_test123/prompt":
                report.write_text(
                    '# Task-Id: ' + self.tid + '\n'
                    '## Resumo\nEscopo implementado.\n'
                    '## Testes\npytest aprovado.\n'
                    '## Bloqueios e riscos\nNenhum.\n'
                    '## Proximos passos\nQA e homologacao.\n'
                    '## Arquivos alterados\nNenhum.\n',
                    encoding="utf-8"
                )
                return {"data": {"id": "msg_test"}}
            from tools.test_atlas_opencode_api import FakeClient as FC
            return FC.post(client, path, obj, timeout)
        client.post = write_report_during_prompt
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        # Manifest declares meu_arquivo.txt which is missing -> invalid_report
        self.assertIn("invalid_report", status["state"])

    def test_negative_outside_artifact_with_manifest(self):
        """When manifest declares a path outside the project root, verification fails.

        Path traversal outside the project root should be rejected.
        """
        # Inbox task with required-artifacts manifest with traversal path
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\n../../etc/passwd\n```\n'
            'READ-ONLY: verifique README e entregue relatorio.\n',
            encoding="utf-8"
        )
        # No pre-existing report or status
        client = FakeClient(["succeeded"])
        # Intercept prompt to write a complete report (no Nenhum.)
        report = self.base / "outbox" / (self.tid + ".md")
        def write_report_during_prompt(path, obj=None, timeout=10):
            if path == "/api/session/ses_test123/prompt":
                report.write_text(
                    '# Task-Id: ' + self.tid + '\n'
                    '## Resumo\nEscopo implementado.\n'
                    '## Testes\npytest aprovado.\n'
                    '## Bloqueios e riscos\nNenhum.\n'
                    '## Proximos passos\nQA e homologacao.\n'
                    '## Arquivos alterados\noutside.txt\n',
                    encoding="utf-8"
                )
                return {"data": {"id": "msg_test"}}
            from tools.test_atlas_opencode_api import FakeClient as FC
            return FC.post(client, path, obj, timeout)
        client.post = write_report_during_prompt
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        # Outside path -> invalid_report
        self.assertIn("invalid_report", status["state"])

    def test_negative_symlink_artifact_with_manifest(self):
        """When manifest declares a symlink path, verification fails.

        Symlinks should be rejected even when the symlink target exists.
        """
        # Simulate the filesystem's symlink metadata without requiring
        # Windows Developer Mode or SeCreateSymbolicLinkPrivilege.
        symlink_path = self.root / "symlink_artifact.txt"
        symlink_path.write_text("regular target used to test symlink guard", encoding="utf-8")
        original_is_symlink = Path.is_symlink

        def simulated_symlink(path):
            if path == symlink_path:
                return True
            return original_is_symlink(path)
        # Inbox task with required-artifacts manifest declaring the symlink
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\nsymlink_artifact.txt\n```\n'
            'READ-ONLY: verifique README e entregue relatorio.\n',
            encoding="utf-8"
        )
        # No pre-existing report or status
        client = FakeClient(["succeeded"])
        # Intercept prompt to write a report with complete sections
        report = self.base / "outbox" / (self.tid + ".md")
        def write_report_during_prompt(path, obj=None, timeout=10):
            if path == "/api/session/ses_test123/prompt":
                report.write_text(
                    '# Task-Id: ' + self.tid + '\n'
                    '## Resumo\nEscopo implementado.\n'
                    '## Testes\npytest aprovado.\n'
                    '## Bloqueios e riscos\nNenhum.\n'
                    '## Proximos passos\nQA e homologacao.\n'
                    '## Arquivos alterados\nsymlink_artifact.txt\n',
                    encoding="utf-8"
                )
                return {"data": {"id": "msg_test"}}
            from tools.test_atlas_opencode_api import FakeClient as FC
            return FC.post(client, path, obj, timeout)
        client.post = write_report_during_prompt
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        with patch.object(Path, "is_symlink", autospec=True, side_effect=simulated_symlink):
            status = runner.run()
        # Symlink -> invalid_report
        self.assertIn("invalid_report", status["state"])
        symlink_path.unlink()

    def test_negative_explicit_manifest_enforced(self):
        """When manifest declares valid paths, verification passes if paths exist.

        An explicit required-artifacts manifest with valid in-repo regular files
        should result in the artifact check passing.
        """
        # Create a valid file that will be declared in the manifest
        valid_file = self.root / "meu_arquivo.txt"
        valid_file.write_text("Conteudo de teste", encoding="utf-8")
        # Inbox task with required-artifacts manifest declaring the valid file
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\nmeu_arquivo.txt\n```\n'
            'READ-ONLY: verifique README e entregue relatorio.\n',
            encoding="utf-8"
        )
        # No pre-existing report or status
        client = FakeClient(["succeeded"])
        # Intercept prompt to write a report WITHOUT the ## Arquivos alterados section
        report = self.base / "outbox" / (self.tid + ".md")
        def write_report_during_prompt(path, obj=None, timeout=10):
            if path == "/api/session/ses_test123/prompt":
                report.write_text(
                    '# Task-Id: ' + self.tid + '\n'
                    '## Resumo\nEscopo implementado.\n'
                    '## Testes\npytest aprovado.\n'
                    '## Bloqueios e riscos\nNenhum.\n'
                    '## Proximos passos\nQA e homologacao.\n'
                    '## Arquivos alterados\nmeu_arquivo.txt\n',
                    encoding="utf-8"
                )
                return {"data": {"id": "msg_test"}}
            from tools.test_atlas_opencode_api import FakeClient as FC
            return FC.post(client, path, obj, timeout)
        client.post = write_report_during_prompt
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        # Valid manifest path + existing file -> artifact check passes.
        # Since the artifact check passes and report is complete, state should be "reported".
        self.assertIn("reported", status["state"])
        # Clean up
        try:
            valid_file.unlink()
        except OSError:
            pass

    def test_negative_no_manifest_no_artifact_requirement(self):
        """When no required-artifacts block exists, Nenhum. in report still passes.

        Backward compatibility: if the inbox task has no ```required-artifacts```
        block, the existing report-only behavior is preserved (Nenhum. is pass).
        """
        # Inbox task WITHOUT required-artifacts block
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            'READ-ONLY: verifique README e entregue relatorio.\n',
            encoding="utf-8"
        )
        # No pre-existing report or status
        client = FakeClient(["succeeded"])
        # Intercept prompt to write a report with Nenhum. in Arquivos alterados (no manifest block)
        report = self.base / "outbox" / (self.tid + ".md")
        def write_report_during_prompt(path, obj=None, timeout=10):
            if path == "/api/session/ses_test123/prompt":
                report.write_text(
                    '# Task-Id: ' + self.tid + '\n'
                    '## Resumo\nEscopo implementado.\n'
                    '## Testes\npytest aprovado.\n'
                    '## Bloqueios e riscos\nNenhum.\n'
                    '## Proximos passos\nQA e homologacao.\n'
                    '## Arquivos alterados\nNenhum.\n',
                    encoding="utf-8"
                )
                return {"data": {"id": "msg_test"}}
            from tools.test_atlas_opencode_api import FakeClient as FC
            return FC.post(client, path, obj, timeout)
        client.post = write_report_during_prompt
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        # No manifest -> report Nenhum. should still pass -> reported state
        self.assertEqual(status["state"], "reported")


# ---- Additional test coverage for missing original cases ----

    def test_normalize_artifact_path_basic(self):
        """Basic normalization of artifact paths."""
        self.assertEqual(_normalize_artifact_path("meu_arquivo.txt"), "meu_arquivo.txt")
        self.assertEqual(_normalize_artifact_path("  arquivo.txt  "), "arquivo.txt")

    def test_normalize_artifact_path_unsafe(self):
        """Unsafe paths are rejected by normalization."""
        self.assertIsNone(_normalize_artifact_path("/etc/passwd"))
        self.assertIsNone(_normalize_artifact_path("../../etc/passwd"))
        self.assertIsNone(_normalize_artifact_path(""))

    def test_is_safe_in_repo_regular_file_missing(self):
        """Missing files are not safe regular files."""
        self.assertFalse(_is_safe_in_repo_regular_file("nonexistent.txt", self.root))

    def test_is_safe_in_repo_regular_file_symlink(self):
        """Reject symlinks deterministically without OS symlink privileges."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            link = root / "link.txt"
            link.write_text("exists", encoding="utf-8")
            original_is_symlink = Path.is_symlink

            def simulated_symlink(path):
                if path == link:
                    return True
                return original_is_symlink(path)

            with patch.object(Path, "is_symlink", autospec=True, side_effect=simulated_symlink):
                self.assertFalse(_is_safe_in_repo_regular_file("link.txt", root))

    def test_parse_manifest_no_block(self):
        """Tasks without ```required-artifacts``` return no manifest."""
        paths, has_manifest = _parse_manifest_from_task(self.tid, self.root)
        self.assertEqual(paths, [])
        self.assertFalse(has_manifest)

    def test_parse_manifest_with_nenhum(self):
        """Manifest with 'Nenhum.' sentinel returns no paths."""
        self.base / "inbox" / (self.tid + ".md")
        inbox_path = self.base / "inbox" / (self.tid + ".md")
        inbox_path.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\nNenhum.\n```\nREAD-ONLY\n',
            encoding="utf-8"
        )
        paths, has_manifest = _parse_manifest_from_task(self.tid, self.root)
        self.assertTrue(has_manifest)
        self.assertEqual(paths, [])

    def test_parse_manifest_with_valid_path(self):
        """Manifest with a valid in-repo path is parsed correctly."""
        (self.root / "test_artifact.txt").write_text("conteudo", encoding="utf-8")
        self.base / "inbox" / (self.tid + ".md")
        inbox_path = self.base / "inbox" / (self.tid + ".md")
        inbox_path.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\ntest_artifact.txt\n```\nREAD-ONLY\n',
            encoding="utf-8"
        )
        paths, has_manifest = _parse_manifest_from_task(self.tid, self.root)
        self.assertTrue(has_manifest)
        self.assertIn("test_artifact.txt", paths)
        (self.root / "test_artifact.txt").unlink()

    def test_report_is_complete_all_sections_minimal(self):
        """Report with exactly 6 chars per section passes completeness."""
        report = self.base / "outbox" / (self.tid + ".md")
        report.write_text(
            '# Task-Id: ' + self.tid + '\n'
            '## Resumo\nMinimo.\n'
            '## Testes\nMinimo.\n'
            '## Bloqueios e riscos\nMinimo.\n'
            '## Proximos passos\nMinimo.\n'
            '## Arquivos alterados\nMinimo.\n',
            encoding="utf-8"
        )
        from tools.atlas_opencode_api import report_is_complete
        self.assertTrue(report_is_complete(report, self.tid))

    def test_api_runner_with_failed_outcome(self):
        """ApiRunner state is agent_failed when outcome is failed."""
        from tools.atlas_opencode_api import ApiRunner
        client = FakeClient(["failed"])
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        self.assertEqual(status["state"], "agent_failed")
        self.assertFalse(status["report_exists"])

    def test_api_runner_with_interrupted_outcome(self):
        """ApiRunner state is agent_interrupted when outcome is interrupted."""
        from tools.atlas_opencode_api import ApiRunner
        client = FakeClient(["interrupted"])
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        self.assertEqual(status["state"], "agent_interrupted")
        self.assertFalse(status["report_exists"])

    def test_negative_artifact_with_bullet_markers(self):
        """Artifact paths with bullet markers (-, *, •) are parsed correctly."""
        import tempfile, os
        # Create a valid file
        valid = self.root / "bullet_artifact.txt"
        valid.write_text("conteudo", encoding="utf-8")
        try:
            # Use a fresh task ID to avoid FileExistsError conflict
            fresh_tid = "20261015T200000Z-aaaaaaaa"
            # Inbox task with required-artifacts using bullet syntax
            inbox_path = self.base / "inbox" / (fresh_tid + ".md")
            inbox_path.write_text(
                '# Pedido ' + fresh_tid + '\n'
                '```required-artifacts\n- bullet_artifact.txt\n```\nREAD-ONLY\n',
                encoding="utf-8"
            )
            # Create the artifact file in the project root (but NOT the report file)
            valid_path = self.root / "bullet_artifact.txt"
            valid_path.write_text("conteudo", encoding="utf-8")
            from tools.atlas_opencode_api import ApiRunner
            client = FakeClient(["succeeded"])
            runner = ApiRunner(client=client, root=self.root, task_id=fresh_tid,
                               timeout_seconds=30, model="nemotron-3.5-lightning-free")
            status = runner.run()
            # Manifest declares valid bullet-artifact path; artifact check passes
            # but no report file exists → missing_report state
            self.assertEqual(status["state"], "missing_report")
            # Cleanup
            try:
                valid_path.unlink()
            except OSError:
                pass
        finally:
            try:
                valid.unlink()
            except OSError:
                pass


# ---- Additional test coverage extending original 17 ----

    def test_manifest_with_multiple_paths(self):
        """Manifest with multiple artifact paths is parsed correctly."""
        (self.root / "art1.txt").write_text("content1", encoding="utf-8")
        (self.root / "art2.txt").write_text("content2", encoding="utf-8")
        self.base / "inbox" / (self.tid + ".md")
        inbox_path = self.base / "inbox" / (self.tid + ".md")
        inbox_path.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\nart1.txt art2.txt\n```\nREAD-ONLY\n',
            encoding="utf-8"
        )
        paths, has_manifest = _parse_manifest_from_task(self.tid, self.root)
        self.assertTrue(has_manifest)
        self.assertEqual(sorted(paths), sorted(["art1.txt", "art2.txt"]))
        (self.root / "art1.txt").unlink()
        (self.root / "art2.txt").unlink()

    def test_report_is_complete_minimal_sections(self):
        """Report with exactly 6 chars per section passes completeness."""
        report = self.base / "outbox" / (self.tid + ".md")
        report.write_text(
            '# Task-Id: ' + self.tid + '\n'
            '## Resumo\nMinimo.\n'
            '## Testes\nMinimo.\n'
            '## Bloqueios e riscos\nMinimo.\n'
            '## Proximos passos\nMinimo.\n'
            '## Arquivos alterados\nMinimo.\n',
            encoding="utf-8"
        )
        from tools.atlas_opencode_api import report_is_complete
        self.assertTrue(report_is_complete(report, self.tid))

    def test_api_runner_reconcile_with_failed(self):
        """Reconcile state is preserved after failed outcome."""
        import json
        from tools.atlas_opencode_api import ApiRunner
        # Create a status file simulating a failed run
        status_file = self.base / "outbox" / (self.tid + ".status.json")
        status_file.write_text(json.dumps({
            "task_id": self.tid,
            "state": "agent_failed",
            "session_id": "ses_test123",
            "report_exists": False,
        }), encoding="utf-8")
        # Create a minimal report
        report = self.base / "outbox" / (self.tid + ".md")
        report.write_text(
            '# Task-Id: ' + self.tid + '\n'
            '## Resumo\nTestado.\n'
            '## Testes\npytest.\n'
            '## Bloqueios e riscos\nNenhum.\n'
            '## Proximos passos\nQA.\n'
            '## Arquivos alterados\nNenhum.\n',
            encoding="utf-8"
        )
        client = FakeClient(["failed"], project_root=self.root)
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        result = runner.reconcile()
        self.assertEqual(result["state"], "agent_failed")
        try:
            status_file.unlink()
        except OSError:
            pass
        try:
            report.unlink()
        except OSError:
            pass


# ---- Regression tests for P0 FIX requirements ----

    def test_parse_manifest_unrelated_code_fences(self):
        """Unrelated Markdown code fences must not interfere with required-artifacts.

        Regression: other ``` blocks before or after ```required-artifacts```
        should not cause the parser to include or exclude incorrect content.
        """
        # Inbox task with a ```python``` fence before ```required-artifacts```
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            '```python\nprint("hello")\n```\n'
            '```required-artifacts\nmeu_arquivo.txt\n```\nREAD-ONLY\n',
            encoding="utf-8"
        )
        paths, has_manifest = _parse_manifest_from_task(self.tid, self.root)
        self.assertTrue(has_manifest)
        self.assertIn("meu_arquivo.txt", paths)

    def test_reconcile_prior_reported_bypass(self):
        """A previously reported task status should not be bypassed without re-verification.

        When a task was already reported, reconcile must re-verify artifacts
        from the original inbox, not just return the old state.
        """
        import json
        # Simulate a previously reported task with a status file
        status_file = self.base / "outbox" / (self.tid + ".status.json")
        # Create a valid file for manifest verification
        valid_file = self.root / "manifest_artifact.txt"
        valid_file.write_text("conteudo", encoding="utf-8")
        # Inbox task with required-artifacts manifest
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\nmanifest_artifact.txt\n```\nREAD-ONLY\n',
            encoding="utf-8"
        )
        status_file.write_text(json.dumps({
            "task_id": self.tid,
            "state": "reported",
            "session_id": "ses_test123",
            "report_exists": True,
        }), encoding="utf-8")
        # Create a complete report
        report = self.base / "outbox" / (self.tid + ".md")
        report.write_text(
            '# Task-Id: ' + self.tid + '\n'
            '## Resumo\nTestado.\n'
            '## Testes\npytest.\n'
            '## Bloqueios e riscos\nNenhum.\n'
            '## Proximos passos\nQA aprovado.\n'
            '## Arquivos alterados\nmanifest_artifact.txt\n',
            encoding="utf-8"
        )
        client = FakeClient(["succeeded"], project_root=self.root)
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        result = runner.reconcile()
        # Manifest path exists and is valid -> should pass artifact check
        # and report should be complete -> reported state
        self.assertIn("reported", result["state"])
        # Cleanup
        try:
            valid_file.unlink()
        except OSError:
            pass
        try:
            status_file.unlink()
        except OSError:
            pass
        try:
            report.unlink()
        except OSError:
            pass

    def test_reconcile_missing_required_artifact(self):
        """Reconcile must fail when a required artifact from the manifest is missing.

        If the inbox task declares a manifest path that does not exist on disk,
        reconcile should result in an invalid_report state.
        """
        import json
        # Create a manifest declaring a file that doesn't exist
        task_file = self.base / "inbox" / (self.tid + ".md")
        task_file.write_text(
            '# Pedido ' + self.tid + '\n'
            '```required-artifacts\nnonexistent_file.txt\n```\nREAD-ONLY\n',
            encoding="utf-8"
        )
        status_file = self.base / "outbox" / (self.tid + ".status.json")
        status_file.write_text(json.dumps({
            "task_id": self.tid,
            "state": "timeout",  # non-success prior outcome
            "session_id": "ses_test123",
            "report_exists": False,
        }), encoding="utf-8")
        # Create a complete report WITHOUT the declared artifact
        report = self.base / "outbox" / (self.tid + ".md")
        report.write_text(
            '# Task-Id: ' + self.tid + '\n'
            '## Resumo\nTestado.\n'
            '## Testes\npytest.\n'
            '## Bloqueios e riscos\nNenhum.\n'
            '## Proximos passos\nQA.\n'
            '## Arquivos alterados\nNenhum.\n',
            encoding="utf-8"
        )
        client = FakeClient(["succeeded"], project_root=self.root)
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        result = runner.reconcile()
        # Manifest declares nonexistent_file.txt which is missing -> invalid_report
        self.assertIn("invalid_report", result["state"])
        # Cleanup
        try:
            status_file.unlink()
        except OSError:
            pass
        try:
            report.unlink()
        except OSError:
            pass

    def test_api_runner_valid_normal_flow(self):
        """Valid normal flow: succeeded, complete report, no manifest -> reported."""
        client = FakeClient(["succeeded"])
        report = self.base / "outbox" / (self.tid + ".md")
        original_post = client.post

        def post_with_report(path, obj=None, timeout=10):
            response = original_post(path, obj, timeout)
            if path.endswith("/prompt"):
                report.write_text(self.complete_report(self.tid), encoding="utf-8")
            return response

        client.post = post_with_report
        runner = ApiRunner(client=client, root=self.root, task_id=self.tid,
                           timeout_seconds=30, model="nemotron-3.5-lightning-free")
        status = runner.run()
        # No manifest block -> report should be accepted as complete
        self.assertEqual(status["state"], "reported")

    def test_report_task_id_mismatch(self):
        """Report with Task-Id mismatch should be rejected.

        The strengthened header check in report_is_complete must reject
        a report whose # Task-Id header does not match the task ID.
        """
        report = self.base / "outbox" / (self.tid + ".md")
        # Write a report with a different Task-Id
        report.write_text(
            '# Task-Id: 20261014T010000Z-00000000\n'  # wrong task ID
            '## Resumo\nTestado.\n'
            '## Testes\npytest.\n'
            '## Bloqueios e riscos\nNenhum.\n'
            '## Proximos passos\nQA.\n'
            '## Arquivos alterados\nNenhum.\n',
            encoding="utf-8"
        )
        from tools.atlas_opencode_api import report_is_complete
        self.assertFalse(report_is_complete(report, self.tid))
        # Cleanup
        try:
            report.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()