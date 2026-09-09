import subprocess
import unittest

from infrastructure.pentium.atlas.config_hermes import HermesConfig
from infrastructure.pentium.atlas.hermes_adapter import HermesAdapter
from infrastructure.pentium.atlas.modelo_llm_gateway import ErroInferencia, SolicitacaoInferencia


class HermesAdapterTests(unittest.TestCase):
    def cfg(self, **overrides):
        values = dict(schema_version=1, provider="openai-codex", profile="atlas", binary="hermes", timeout_s=2.0, max_context_tokens=4096, max_response_bytes=4096)
        values.update(overrides)
        return HermesConfig(**values)

    def req(self):
        return SolicitacaoInferencia(1, "formular_resposta_cognitiva", '{"estado_tecnico":"healthy"}', 4096, "off")

    def test_invokes_dedicated_profile_and_codex_provider(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, stdout='{"versao_schema":1}', stderr="")
        result = HermesAdapter(self.cfg(), runner=runner).inferir(self.req())
        self.assertTrue(result.sucesso)
        self.assertEqual("hermes/openai-codex", result.backend)
        command, kwargs = calls[0]
        self.assertEqual(["hermes", "-p", "atlas", "-z"], command[:4])
        self.assertEqual(["--provider", "openai-codex"], command[-2:])
        joined = " ".join(command).lower()
        self.assertNotIn("--yolo", joined)
        self.assertNotIn("--toolsets", joined)
        self.assertEqual(2.0, kwargs["timeout"])

    def test_timeout_is_bounded_failure(self):
        def runner(*_args, **_kwargs):
            raise subprocess.TimeoutExpired("hermes", 2.0)
        result = HermesAdapter(self.cfg(), runner=runner).inferir(self.req())
        self.assertFalse(result.sucesso)
        self.assertEqual(ErroInferencia.TIMEOUT, result.erro)

    def test_oversized_response_is_rejected(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout="x" * 32, stderr="")
        result = HermesAdapter(self.cfg(max_response_bytes=16), runner=runner).inferir(self.req())
        self.assertFalse(result.sucesso)
        self.assertEqual(ErroInferencia.LIMITE_EXCEDIDO, result.erro)

    def test_process_failure_does_not_leak_stderr(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="oauth_token=secret")
        result = HermesAdapter(self.cfg(), runner=runner).inferir(self.req())
        self.assertFalse(result.sucesso)
        self.assertEqual(ErroInferencia.BACKEND_INDISPONIVEL, result.erro)
        self.assertIsNone(result.texto)


if __name__ == "__main__":
    unittest.main()
