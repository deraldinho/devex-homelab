import unittest
from types import SimpleNamespace
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import ContextoCognitivo, MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.hermes_adapter import HermesAdapter
from infrastructure.pentium.atlas.config_hermes import HermesConfig
from infrastructure.pentium.atlas.modelo_llm_gateway import SolicitacaoInferencia

class TestWorkingMemoryDialogue(unittest.TestCase):
    def test_working_memory_injected_in_hermes_prompt(self):
        cfg = HermesConfig(
            schema_version=1,
            provider="openai-codex",
            profile="test",
            binary="hermes",
            timeout_s=10.0,
            max_context_tokens=4096,
            max_response_bytes=1024
        )
        adapter = HermesAdapter(cfg)

        contexto = {
            "estado_tecnico": "healthy",
            "emocao_principal": "curioso",
            "nuances": ["empolgado"],
            "estado_afetivo": {"valencia": 0.8, "estresse": 0.1, "curiosidade": 0.9, "confianca": 0.85},
            "mensagem_usuario": "Atlas, o que você acha dessa arquitetura?",
            "historico_conversa": [
                {"role": "user", "message": "Olá Atlas, como você está?"},
                {"role": "atlas", "message": "Olá operador, meu organismo segue calmo e em harmonia."}
            ]
        }

        req = SolicitacaoInferencia(
            versao_schema=1,
            tarefa="formular_resposta_cognitiva",
            contexto_json=str(contexto).replace("'", "\""),
            max_tokens_contexto=4096
        )

        prompt = adapter._prompt(req)
        self.assertIn("<affective_state_governor>", prompt)
        self.assertIn("CURIOSO", prompt)
        self.assertIn("<recent_conversation_history>", prompt)
        self.assertIn("Operador: Olá Atlas, como você está?", prompt)
        self.assertIn("Atlas: Olá operador, meu organismo segue calmo e em harmonia.", prompt)
        self.assertIn("Atlas, o que você acha dessa arquitetura?", prompt)

    def test_proprioceptive_trends_and_hypotheses_injected_in_hermes_prompt(self):
        cfg = HermesConfig(
            schema_version=1,
            provider="openai-codex",
            profile="test",
            binary="hermes",
            timeout_s=10.0,
            max_context_tokens=4096,
            max_response_bytes=1024,
        )
        adapter = HermesAdapter(cfg)

        contexto = {
            "estado_tecnico": "busy",
            "emocao_principal": "atento",
            "nuances": ["vigilante"],
            "estado_afetivo": {"valencia": 0.2, "estresse": 0.3, "curiosidade": 0.7, "confianca": 0.8},
            "mensagem_usuario": "Atlas, como está a memória?",
            "tendencias_relevantes": [
                {
                    "metrica": "pentium:ram_percent",
                    "direcao": "rising",
                    "inclinacao": 0.05,
                    "confianca": 0.95,
                    "horas_para_esgotamento": 4.5,
                    "z_score_atual": 2.8,
                    "correlacao_causal": "l2j_latency_spike",
                    "interpretacao_diagnostica": "Gargalo de memória gerando contenção de I/O",
                }
            ],
            "hipoteses_ativas": [
                {
                    "hypothesis_id": "hypo-leak-pentium",
                    "title": "Vazamento gradual de RAM no coletor",
                    "status": "investigating",
                    "confidence": 0.85,
                }
            ],
        }

        req = SolicitacaoInferencia(
            versao_schema=1,
            tarefa="formular_resposta_cognitiva",
            contexto_json=str(contexto).replace("'", "\""),
            max_tokens_contexto=4096,
        )

        prompt = adapter._prompt(req)
        self.assertIn("<proprioceptive_trends>", prompt)
        self.assertIn("pentium:ram_percent", prompt)
        self.assertIn("RISING", prompt)
        self.assertIn("Esgotamento projetado: 4.5h", prompt)
        self.assertIn("Gargalo de memória gerando contenção de I/O", prompt)
        self.assertIn("<active_hypotheses>", prompt)
        self.assertIn("[INVESTIGATING] hypo-leak-pentium: Vazamento gradual de RAM no coletor", prompt)


if __name__ == "__main__":
    unittest.main()
