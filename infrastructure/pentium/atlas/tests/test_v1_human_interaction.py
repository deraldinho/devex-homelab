import unittest

from infrastructure.pentium.atlas.human_interaction import HumanInteractionGateway


class FakeLoop:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def processar(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class Resp:
    texto = "Estou ouvindo."
    razao = None


class HumanInteractionGatewayTests(unittest.TestCase):
    def test_human_text_becomes_bounded_stimulus_and_cognitive_activation(self):
        loop = FakeLoop(Resp())
        context = {"mudancas_recentes": [], "other": "ok"}
        gateway = HumanInteractionGateway(loop, context_provider=lambda: context, max_text_chars=64)
        text = gateway.handle("como esta o x99?")
        self.assertEqual("Estou ouvindo.", text)
        call = loop.calls[0]
        self.assertTrue(call["sinais_ativacao"]["interacao_humana"])
        stimulus = call["dados_contexto"]["mudancas_recentes"][-1]
        self.assertEqual("human_interaction", stimulus.kind)
        self.assertEqual("como esta o x99?", stimulus.payload["text"])

    def test_oversized_text_is_rejected_before_cognition(self):
        loop = FakeLoop(Resp())
        gateway = HumanInteractionGateway(loop, context_provider=lambda: {"mudancas_recentes": []}, max_text_chars=4)
        with self.assertRaises(ValueError):
            gateway.handle("cinco")
        self.assertEqual([], loop.calls)


if __name__ == "__main__":
    unittest.main()

class RespLlmDown:
    texto = None
    razao = "llm_indisponivel"


class HumanInteractionFallbackTests(unittest.TestCase):
    def test_llm_unavailable_still_returns_explicit_voice_fallback(self):
        gateway = HumanInteractionGateway(FakeLoop(RespLlmDown()), context_provider=lambda: {"mudancas_recentes": []}, max_text_chars=64)
        text = gateway.handle("voce esta me ouvindo?")
        self.assertEqual("Estou ouvindo, mas meu modulo de linguagem esta indisponivel.", text)
