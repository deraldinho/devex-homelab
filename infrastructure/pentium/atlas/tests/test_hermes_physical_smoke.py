import subprocess
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.hermes_physical_smoke import HermesPhysicalSmoke


class HermesPhysicalSmokeTests(unittest.TestCase):
    def test_rejects_when_voice_is_active_before_inference(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            if command[:3] == ["git", "-C", str(Path("/repo"))]:
                return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")
            if command[:3] == ["systemctl", "--user", "is-active"]:
                return subprocess.CompletedProcess(command, 0, "active\n", "")
            raise AssertionError(command)
        result = HermesPhysicalSmoke(runner=runner).check_runtime(
            repo_root=Path("/repo"), expected_sha="a" * 40
        )
        self.assertFalse(result.ok)
        self.assertEqual("voice_active", result.reason)

    def test_rejects_wrong_sha_without_model_call(self):
        def runner(command, **kwargs):
            if command[0] == "git":
                return subprocess.CompletedProcess(command, 0, "b" * 40 + "\n", "")
            raise AssertionError(command)
        result = HermesPhysicalSmoke(runner=runner).check_runtime(
            repo_root=Path("/repo"), expected_sha="a" * 40
        )
        self.assertFalse(result.ok)
        self.assertEqual("sha_mismatch", result.reason)

    def test_accepts_exact_sha_with_voice_inactive(self):
        def runner(command, **kwargs):
            if command[0] == "git":
                return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")
            if command[:3] == ["systemctl", "--user", "is-active"]:
                return subprocess.CompletedProcess(command, 3, "inactive\n", "")
            raise AssertionError(command)
        result = HermesPhysicalSmoke(runner=runner).check_runtime(
            repo_root=Path("/repo"), expected_sha="a" * 40
        )
        self.assertTrue(result.ok)
        self.assertEqual("a" * 40, result.sha)


if __name__ == "__main__":
    unittest.main()

class HermesPhysicalSmokeOutputTests(unittest.TestCase):
    def test_success_output_contains_only_certification_metadata(self):
        valid = ('{"versao_schema":1,"texto":"segredo-nao-deve-vazar","resumo":null,'
                 '"intencao":null,"parametros_intencao":{},"confianca":1,'
                 '"motivo":"smoke","requer_confirmacao":false}')
        def runner(command, **kwargs):
            if command[0] == "git":
                return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")
            if command[:3] == ["systemctl", "--user", "is-active"]:
                return subprocess.CompletedProcess(command, 3, "inactive\n", "")
            if command[1:3] == ["profile", "show"]:
                return subprocess.CompletedProcess(command, 0, "Profile: atlas\n", "")
            if "prompt-size" in command:
                return subprocess.CompletedProcess(command, 0, "Tool schemas : 2 B (0 tools)\n", "")
            if "-z" in command:
                return subprocess.CompletedProcess(command, 0, valid, "oauth_token=secret")
            raise AssertionError(command)
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config_hermes.json"
            cfg.write_text(json.dumps({
                "schema_version": 1, "provider": "openai-codex", "profile": "atlas",
                "binary": "hermes", "timeout_s": 2.0, "max_context_tokens": 4096,
                "max_response_bytes": 16384,
            }), encoding="utf-8")
            output = HermesPhysicalSmoke(runner=runner).execute(
                repo_root=Path("/repo"), expected_sha="a" * 40, hermes_config=cfg
            )
        self.assertTrue(output["ok"])
        self.assertEqual(0, output["tool_count"])
        rendered = repr(output)
        self.assertNotIn("segredo-nao-deve-vazar", rendered)
        self.assertNotIn("oauth_token", rendered)


class HermesPhysicalSmokeVoiceEnabledTests(unittest.TestCase):
    def runner(self, voice_active: bool):
        def run(command, **kwargs):
            if command[0] == "git":
                return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")
            if command[:3] == ["systemctl", "--user", "is-active"]:
                if voice_active:
                    return subprocess.CompletedProcess(command, 0, "active\n", "")
                return subprocess.CompletedProcess(command, 3, "inactive\n", "")
            raise AssertionError(command)
        return run

    def test_accepts_active_voice_when_expected(self):
        result = HermesPhysicalSmoke(runner=self.runner(True)).check_runtime(
            repo_root=Path("/repo"), expected_sha="a" * 40,
            voice_expected_active=True,
        )
        self.assertTrue(result.ok)

    def test_rejects_inactive_voice_when_active_is_expected(self):
        result = HermesPhysicalSmoke(runner=self.runner(False)).check_runtime(
            repo_root=Path("/repo"), expected_sha="a" * 40,
            voice_expected_active=True,
        )
        self.assertFalse(result.ok)
        self.assertEqual("voice_inactive", result.reason)


class HermesPhysicalSmokeVoiceCliTests(unittest.TestCase):
    def test_parser_accepts_voice_expected_active_flag(self):
        from infrastructure.pentium.atlas.hermes_physical_smoke import construir_parser
        args = construir_parser().parse_args([
            "--repo-root", "/repo",
            "--expected-sha", "a" * 40,
            "--hermes-config", "/tmp/hermes.json",
            "--voice-expected-active",
        ])
        self.assertTrue(args.voice_expected_active)
