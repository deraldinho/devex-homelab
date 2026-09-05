import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class C5PhysicalOrchestratorContractTests(unittest.TestCase):
    def test_orquestrador_e_python_sem_shell_e_exige_sha_modelo_binario(self):
        texto = (ROOT / "infrastructure/pentium/atlas/c5_physical_orchestrator.py").read_text(encoding="utf-8")
        self.assertIn("--expected-sha", texto)
        self.assertIn("--llama-server", texto)
        self.assertIn("--model", texto)
        self.assertIn("LlamaCppServerRuntime", texto)
        self.assertIn("c5_physical_runner", texto)
        self.assertNotIn("shell=True", texto)
        self.assertNotIn("os.system", texto)
        self.assertNotIn("ssh ", texto)

    def test_orquestrador_nao_baixa_modelo_nem_emite_physical_pass(self):
        texto = (ROOT / "infrastructure/pentium/atlas/c5_physical_orchestrator.py").read_text(encoding="utf-8")
        self.assertNotIn("http://", texto)
        self.assertNotIn("https://", texto)
        self.assertNotIn("PHYSICAL_PASS", texto)


if __name__ == "__main__":
    unittest.main()
