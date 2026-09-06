import unittest

from infrastructure.pentium.atlas.c5_physical_evaluator import (
    C5PhysicalBudget,
    C5PhysicalEvidence,
    avaliar_c5_fisica,
)


class C5PhysicalEvaluatorTests(unittest.TestCase):
    def _evidence(self):
        return C5PhysicalEvidence(
            expected_sha="7" * 40,
            cold={"inferencia_sucesso": True, "latencia_total_ms": 1200, "tokens_por_s": 8.0, "rss_llm_kib": 500000, "rss_atlas_kib": 60000, "swap_usada_kib": 1000, "cpu_percent": 80.0, "temperatura_c": 65.0},
            warm={"inferencia_sucesso": True, "latencia_total_ms": 700, "tokens_por_s": 9.5, "rss_llm_kib": 510000, "rss_atlas_kib": 61000, "swap_usada_kib": 1200, "cpu_percent": 75.0, "temperatura_c": 66.0},
            timeout_isolado=True,
            observation_runtime_preservado=True,
            fila_ativacao_pico=3,
            fila_ativacao_limite=8,
            soak_iteracoes=8,
            soak_falhas=0,
        )

    def test_sem_budget_aprovado_nunca_emite_physical_pass(self):
        resultado = avaliar_c5_fisica(self._evidence(), None)
        self.assertFalse(resultado.aprovado)
        self.assertIn("budget_fisico_nao_aprovado", resultado.blockers)
        self.assertNotEqual("ATLAS_COGNITIVO_C5_PHYSICAL_PASS", resultado.marker)

    def test_evidencia_aprovada_emite_marker_somente_quando_todos_os_gates_passam(self):
        budget = C5PhysicalBudget(
            max_rss_total_kib=700000,
            max_swap_usada_kib=10000,
            max_cpu_percent=95.0,
            max_temperatura_c=80.0,
            max_latencia_cold_ms=2000,
            max_latencia_warm_ms=1500,
            min_tokens_por_s=5.0,
            min_soak_iteracoes=8,
        )
        resultado = avaliar_c5_fisica(self._evidence(), budget)
        self.assertTrue(resultado.aprovado)
        self.assertEqual((), resultado.blockers)
        self.assertEqual("ATLAS_COGNITIVO_C5_PHYSICAL_PASS", resultado.marker)

    def test_falha_de_isolamento_fila_ou_soak_bloqueia_promocao(self):
        base = self._evidence()
        evidence = C5PhysicalEvidence(
            **{**base.__dict__, "timeout_isolado": False, "fila_ativacao_pico": 9, "soak_falhas": 1}
        )
        budget = C5PhysicalBudget(700000, 10000, 95.0, 80.0, 2000, 1500, 5.0, 8)
        resultado = avaliar_c5_fisica(evidence, budget)
        self.assertFalse(resultado.aprovado)
        self.assertIn("timeout_nao_isolado", resultado.blockers)
        self.assertIn("fila_ativacao_excedeu_limite", resultado.blockers)
        self.assertIn("soak_com_falhas", resultado.blockers)


if __name__ == "__main__":
    unittest.main()
