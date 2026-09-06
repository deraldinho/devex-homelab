import unittest

from infrastructure.pentium.atlas.prompt_cognitivo import construir_prompt_cognitivo
from infrastructure.pentium.atlas.modelo_llm_gateway import SolicitacaoInferencia


class PromptCognitivoTests(unittest.TestCase):
    def test_prompt_exige_json_c4_exato_sem_autoridade_tecnica(self):
        req = SolicitacaoInferencia(1, 'formular_resposta_cognitiva', '{"motivo_ativacao":"reflexao_periodica"}', 4096)
        prompt = construir_prompt_cognitivo(req)
        for campo in ('versao_schema', 'texto', 'resumo', 'intencao', 'parametros_intencao', 'confianca', 'motivo', 'requer_confirmacao'):
            self.assertIn(campo, prompt)
        self.assertIn('SOMENTE um objeto JSON', prompt)
        self.assertIn('Nao decida saude tecnica', prompt)
        self.assertIn(req.contexto_json, prompt)
