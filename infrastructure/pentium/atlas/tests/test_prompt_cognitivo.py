import unittest

from infrastructure.pentium.atlas.prompt_cognitivo import construir_prompt_cognitivo
from infrastructure.pentium.atlas.modelo_llm_gateway import SolicitacaoInferencia


class PromptCognitivoTests(unittest.TestCase):
    def test_prompt_exige_json_c4_exato_sem_autoridade_tecnica(self):
        req = SolicitacaoInferencia(1, "formular_resposta_cognitiva", '{"estado":"healthy"}', 4096)
        prompt = construir_prompt_cognitivo(req)
        self.assertIn('"versao_schema"', prompt)
        self.assertIn('"parametros_intencao"', prompt)
        self.assertIn('Nao altere estado tecnico', prompt)
        self.assertIn(req.contexto_json, prompt)


if __name__ == "__main__":
    unittest.main()
