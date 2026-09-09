import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class C5PhysicalOrchestratorContractTests(unittest.TestCase):
    def test_orquestrador_usa_hermes_sem_llama_local(self):
        texto = (ROOT / "infrastructure/pentium/atlas/c5_physical_orchestrator.py").read_text(encoding="utf-8")
        for token in ("--expected-sha", "--hermes-config", "--heartbeat-state", "--soak-iterations",
                      "HermesAdapter", "load_hermes_config", "c5_physical_runner",
                      "C5ObservationProbe", "executar_campanha_c5"):
            self.assertIn(token, texto)
        for legado in ("--llama-server", "--model", "--socket", "LlamaCppServerRuntime", "get_json_unix", '"/health"'):
            self.assertNotIn(legado, texto)
        self.assertNotIn("shell=True", texto)
        self.assertNotIn("os.system", texto)
        self.assertNotIn("ssh ", texto)

    def test_orquestrador_nao_baixa_backend_nem_emite_physical_pass(self):
        texto = (ROOT / "infrastructure/pentium/atlas/c5_physical_orchestrator.py").read_text(encoding="utf-8")
        self.assertNotIn("http://", texto)
        self.assertNotIn("https://", texto)
        self.assertNotIn("PHYSICAL_PASS", texto)


if __name__ == "__main__":
    unittest.main()


class C5HermesPreflightContractTests(unittest.TestCase):
    def test_orchestrator_requires_zero_tools_preflight_before_campaign(self):
        texto = (ROOT / "infrastructure/pentium/atlas/c5_physical_orchestrator.py").read_text(encoding="utf-8")
        self.assertIn("HermesPreflight", texto)
        self.assertIn("preflight.ok", texto)
        self.assertLess(texto.index("HermesPreflight"), texto.index("executar_campanha_c5("))
