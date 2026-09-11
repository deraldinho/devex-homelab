import unittest

from infrastructure.pentium.atlas.modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.reasoning_policy import ReasoningPolicy


class FakeContext:
    def __init__(self, text, motivo=MotivoAtivacaoCognitiva.INTERACAO_HUMANA, incidente=None):
        self.motivo_ativacao = motivo
        self.incidente_principal = incidente
        self.mudancas_recentes = ({"kind": "human_interaction", "payload": {"text": text}},)


class ReasoningPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = ReasoningPolicy()

    def test_simple_human_conversation_uses_off(self):
        self.assertEqual("off", self.policy.select(FakeContext("esta me ouvindo?"), "formular_resposta_cognitiva"))

    def test_explicit_analysis_uses_on(self):
        self.assertEqual("on", self.policy.select(FakeContext("analise por que o x99 caiu tres vezes"), "formular_resposta_cognitiva"))

    def test_ambiguous_technical_question_uses_auto(self):
        self.assertEqual("auto", self.policy.select(FakeContext("o x99 parece estranho hoje"), "formular_resposta_cognitiva"))

    def test_critical_autonomous_reason_uses_on(self):
        ctx = FakeContext("", MotivoAtivacaoCognitiva.CRITICIDADE_TECNICA, incidente={"tipo": "host_unavailable"})
        self.assertEqual("on", self.policy.select(ctx, "formular_resposta_cognitiva"))


if __name__ == "__main__":
    unittest.main()
