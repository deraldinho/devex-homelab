import json
import subprocess
import unittest

from infrastructure.pentium.atlas.github_observation import GitHubCliClient, GitHubObservationSource


class FakeClient:
    def repository_snapshot(self, repo):
        return {
            "repo": repo,
            "pull_requests": [{"number": 12, "state": "open", "draft": False, "head_sha": "abc", "updated_at": "2026-09-10T20:00:00Z"}],
            "issues": [{"number": 20, "state": "open", "updated_at": "2026-09-10T20:01:00Z"}],
            "workflow_runs": [{"id": 77, "status": "completed", "conclusion": "success", "head_sha": "abc", "updated_at": "2026-09-10T20:02:00Z"}],
        }


class GitHubObservationTests(unittest.TestCase):
    def test_source_normalizes_repository_delivery_state(self):
        snapshot = GitHubObservationSource("deraldinho/devex-homelab", FakeClient()).poll()
        self.assertEqual("github.deraldinho.devex-homelab", snapshot.source)
        self.assertEqual("healthy", snapshot.status)
        self.assertEqual("abc", snapshot.payload["pull_requests"][0]["head_sha"])
        self.assertEqual("success", snapshot.payload["workflow_runs"][0]["conclusion"])

    def test_source_rejects_invalid_repository_name(self):
        with self.assertRaises(ValueError): GitHubObservationSource("bad repo", FakeClient())

    def test_cli_client_uses_fixed_gh_api_arguments(self):
        calls=[]
        payloads={
            "pulls?state=open&per_page=10": [],
            "issues?state=open&per_page=10": [],
            "actions/runs?per_page=10": {"workflow_runs": []},
        }
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            suffix=command[-1].split("/repos/deraldinho/devex-homelab/",1)[1]
            return subprocess.CompletedProcess(command,0,json.dumps(payloads[suffix]),"")
        result=GitHubCliClient(runner=runner).repository_snapshot("deraldinho/devex-homelab")
        self.assertEqual("deraldinho/devex-homelab",result["repo"])
        self.assertEqual(3,len(calls))
        self.assertTrue(all(call[0][:2]==["gh","api"] for call in calls))
        self.assertTrue(all(call[1]["shell"] is False for call in calls))


if __name__ == "__main__": unittest.main()
