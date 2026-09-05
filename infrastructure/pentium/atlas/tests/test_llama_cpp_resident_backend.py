import unittest
from pathlib import Path

from infrastructure.pentium.atlas.llama_cpp_resident_backend import LlamaCppResidentBackend
from infrastructure.pentium.atlas.modelo_llm_gateway import SolicitacaoInferencia, ResultadoInferencia, ErroInferencia


class Fallback:
    def __init__(self): self.calls = 0
    def inferir(self, req):
        self.calls += 1
        return ResultadoInferencia(True, 'fallback', None, 1, 'llama_cpp')


class ResidentBackendTests(unittest.TestCase):
    def req(self): return SolicitacaoInferencia(1, 'formular', '{"x":1}', 4096)

    def test_envia_completion_com_cache_prompt_e_reuse(self):
        seen = {}
        def requester(sock, path, payload, timeout, max_bytes):
            seen.update(payload); return 200, {"content":"ok"}
        backend = LlamaCppResidentBackend(Path('/tmp/a.sock'), cache_reuse=64, timeout_s=20, requester=requester)
        result = backend.inferir(self.req())
        self.assertTrue(result.sucesso)
        self.assertEqual('ok', result.texto)
        self.assertTrue(seen['cache_prompt'])
        self.assertEqual(64, seen['n_cache_reuse'])
        self.assertEqual(256, seen['n_predict'])

    def test_falha_residente_usa_fallback(self):
        fallback = Fallback()
        backend = LlamaCppResidentBackend(Path('/tmp/a.sock'), cache_reuse=64, timeout_s=20, requester=lambda *a: (_ for _ in ()).throw(OSError()), fallback=fallback)
        result = backend.inferir(self.req())
        self.assertEqual('fallback', result.texto)
        self.assertEqual(1, fallback.calls)
