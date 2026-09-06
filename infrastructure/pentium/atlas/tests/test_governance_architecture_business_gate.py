import unittest
from pathlib import Path


class GovernanceArchitectureBusinessGateTests(unittest.TestCase):
    def test_policies_exigem_coerencia_arquitetura_regras_negocio(self):
        text = Path("docs/governance/policies.md").read_text(encoding="utf-8")
        self.assertIn("Gate de coerencia arquitetural e regras de negocio", text)
        self.assertIn("Divergencia entre codigo, arquitetura, PRD/regra de negocio ou governanca e blocker", text)
        self.assertIn("repetir a verificacao arquitetura <-> regras de negocio", text)


if __name__ == "__main__":
    unittest.main()