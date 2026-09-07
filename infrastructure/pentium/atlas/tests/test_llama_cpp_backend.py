import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from infrastructure.pentium.atlas.llama_cpp_backend import LlamaCppBackend
from infrastructure.pentium.atlas.modelo_llm_gateway import (
    ErroInferencia,
    SolicitacaoInferencia,
)


class ExecutorFake:
    def __init__(self, resultado=None, erro=None):
        self.resultado = resultado or SimpleNamespace(returncode=0, stdout='{"versao_schema":1,"texto":"ok","resumo":null,"intencao":null,"parametros_intencao":{},"confianca":0.9,"motivo":"ok","requer_confirmacao":false}', stderr="")
        self.erro = erro
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self.erro:
            raise self.erro
        return self.resultado


class LlamaCppBackendTests(unittest.TestCase):
    def paths(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        binary = root / "llama-cli"
        model = root / "qwen.gguf"
        binary.write_text("fake", encoding="utf-8")
        model.write_text("fake", encoding="utf-8")
        return td, binary, model

    def test_argv_e_fixo_sem_shell_e_sem_rede(self):
        td, binary, model = self.paths()
        self.addCleanup(td.cleanup)
        executor = ExecutorFake()
        backend = LlamaCppBackend(binary, model, timeout_s=5, max_saida_bytes=1024, executor=executor)
        req = SolicitacaoInferencia(1, "resumir_estado", '{"estado":"healthy"}', 2048)
        out = backend.inferir(req)
        self.assertTrue(out.sucesso)
        argv, kwargs = executor.calls[0]
        self.assertEqual(str(binary), argv[0])
        self.assertIn(str(model), argv)
        self.assertIs(kwargs["shell"], False)
        self.assertNotIn("http", " ".join(argv).lower())

    def test_timeout_e_modelo_ausente_falham_fechado(self):
        td, binary, model = self.paths()
        self.addCleanup(td.cleanup)
        model.unlink()
        backend = LlamaCppBackend(binary, model, timeout_s=1, max_saida_bytes=1024, executor=ExecutorFake())
        out = backend.inferir(SolicitacaoInferencia(1, "x", "{}", 128))
        self.assertFalse(out.sucesso)
        self.assertEqual(ErroInferencia.MODELO_INDISPONIVEL, out.erro)

        model.write_text("fake", encoding="utf-8")
        timeout = subprocess.TimeoutExpired([str(binary)], 1)
        backend = LlamaCppBackend(binary, model, timeout_s=1, max_saida_bytes=1024, executor=ExecutorFake(erro=timeout))
        out = backend.inferir(SolicitacaoInferencia(1, "x", "{}", 128))
        self.assertEqual(ErroInferencia.TIMEOUT, out.erro)

    def test_saida_acima_do_bound_e_rejeitada(self):
        td, binary, model = self.paths()
        self.addCleanup(td.cleanup)
        executor = ExecutorFake(SimpleNamespace(returncode=0, stdout="x" * 200, stderr=""))
        backend = LlamaCppBackend(binary, model, timeout_s=1, max_saida_bytes=32, executor=executor)
        out = backend.inferir(SolicitacaoInferencia(1, "x", "{}", 128))
        self.assertEqual(ErroInferencia.LIMITE_EXCEDIDO, out.erro)


if __name__ == "__main__":
    unittest.main()


class LlamaCppBatchModeTests(LlamaCppBackendTests):
    def test_cli_usa_single_turn_simple_io_e_reasoning_off(self):
        td, binary, model = self.paths()
        self.addCleanup(td.cleanup)
        executor = ExecutorFake()
        backend = LlamaCppBackend(binary, model, timeout_s=5, max_saida_bytes=1024, executor=executor)
        backend.inferir(SolicitacaoInferencia(1, "x", "{}", 256))
        argv, _ = executor.calls[0]
        self.assertIn("--single-turn", argv)
        self.assertIn("--simple-io", argv)
        self.assertEqual(["--reasoning", "off"], argv[argv.index("--reasoning"):argv.index("--reasoning") + 2])
        self.assertIn("--log-disable", argv)
        self.assertIn("--no-display-prompt", argv)
