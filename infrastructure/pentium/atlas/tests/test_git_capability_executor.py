import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.pentium.atlas.git_capability_executor import GitCapabilityExecutor, ClusterVitalsExecutor


class GitCapabilityExecutorTests(unittest.TestCase):
    def test_git_get_status_missing_repo_returns_clean_fallback(self):
        executor = GitCapabilityExecutor(repo_roots={})
        res = executor("git_get_status", {"project": "projeto_inexistente"})
        self.assertEqual("projeto_inexistente", res["project"])
        self.assertEqual("repository_not_found_locally", res["status"])

    def test_git_recent_commits_with_mock_runner(self):
        class MockResult:
            returncode = 0
            stdout = "a1b2c3d feat: add new feature\ne4f5a6b fix: resolve bug\n"
            stderr = ""

        def fake_runner(cmd, **kwargs):
            return MockResult()

        with TemporaryDirectory() as tmp:
            repo_dir = Path(tmp) / "L2jToren"
            repo_dir.mkdir()
            (repo_dir / ".git").mkdir()

            executor = GitCapabilityExecutor(repo_roots={"L2jToren": repo_dir}, runner=fake_runner)
            res = executor("git_recent_commits", {"project": "L2jToren", "count": 2})
            self.assertEqual("L2jToren", res["project"])
            self.assertEqual(2, len(res["commits"]))
            self.assertIn("feat: add new feature", res["commits"][0])


class ClusterVitalsExecutorTests(unittest.TestCase):
    def test_get_cluster_vitals_pentium(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            executor = ClusterVitalsExecutor(state_dir=state_dir)
            res = executor("get_cluster_vitals", {"host": "pentium"})
            self.assertEqual("pentium", res["host"])
            self.assertEqual("healthy", res["status"])

    def test_get_cluster_vitals_core_from_context(self):
        import json
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            ctx_file = state_dir / "cognitive-observation-context.json"
            ctx_file.write_text(json.dumps({
                "recent_changes": [
                    {"source": "core", "kind": "status_changed", "severity": "info", "timestamp": "2026-09-20T00:00:00Z"}
                ]
            }), encoding="utf-8")

            executor = ClusterVitalsExecutor(state_dir=state_dir)
            res = executor("get_cluster_vitals", {"host": "core"})
            self.assertEqual("core", res["host"])
            self.assertEqual("status_changed", res["status"])
            self.assertTrue(res["monitored"])


if __name__ == "__main__":
    unittest.main()
