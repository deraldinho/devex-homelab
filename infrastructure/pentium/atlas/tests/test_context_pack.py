import unittest

from infrastructure.pentium.atlas.context_pack import ContextPackBuilder


class ContextPackTests(unittest.TestCase):
    def setUp(self):
        self.builder = ContextPackBuilder()

    def test_ceiling_normal_e_respeitado(self):
        pack = self.builder.build(mode="normal", human="h" * 4000, observation="o" * 4000, memory=("m" * 4000,), workspace=("w" * 4000,))
        self.assertLessEqual(pack.estimated_tokens, 3000)

    def test_prioridade_preserva_contexto_humano(self):
        pack = self.builder.build(mode="normal", human="pergunta importante", observation="o" * 12000, memory=("m" * 3000,), workspace=("w" * 3000,))
        self.assertIn("pergunta importante", pack.sections["human"])

    def test_delta_substitui_snapshot_completo(self):
        pack = self.builder.build(mode="normal", human="", observation="snapshot completo antigo", observation_delta="voice inactive -> active")
        self.assertEqual("voice inactive -> active", pack.sections["observation"])
        self.assertNotIn("snapshot completo antigo", pack.sections["observation"])

    def test_limites_complexo_e_emergency(self):
        complex_pack = self.builder.build(mode="complex", human="x" * 30000)
        emergency_pack = self.builder.build(mode="emergency", human="x" * 40000)
        self.assertLessEqual(complex_pack.estimated_tokens, 6000)
        self.assertLessEqual(emergency_pack.estimated_tokens, 8000)

    def test_memory_e_workspace_sao_bounded(self):
        pack = self.builder.build(mode="normal", memory=tuple("m" * 1000 for _ in range(10)), workspace=tuple("w" * 1000 for _ in range(10)))
        self.assertLessEqual(len(pack.sections["memory"]), 2400)
        self.assertLessEqual(len(pack.sections["workspace"]), 3200)


if __name__ == "__main__":
    unittest.main()
