import unittest

from infrastructure.pentium.atlas.c5_physical_campaign import executar_campanha_c5


class C5PhysicalCampaignTests(unittest.TestCase):
    def test_executa_cold_warm_timeout_e_soak_bounded_no_mesmo_runtime(self):
        chamadas = []

        def run_once(*, timeout_s, fase):
            chamadas.append((fase, timeout_s))
            if fase == "timeout":
                return {"resultado": {"inferencia_sucesso": False, "erro": "timeout"}}
            return {"resultado": {"inferencia_sucesso": True, "latencia_total_ms": 100, "tokens_por_s": 8.0}}

        evidencia = executar_campanha_c5(
            expected_sha="a" * 40,
            run_once=run_once,
            observation_probe=lambda: True,
            timeout_normal_s=20.0,
            timeout_probe_s=0.001,
            soak_iteracoes=3,
        )
        self.assertEqual(3, evidencia.soak_iteracoes)
        self.assertEqual(0, evidencia.soak_falhas)
        self.assertTrue(evidencia.timeout_isolado)
        self.assertTrue(evidencia.observation_runtime_preservado)
        self.assertEqual(0, evidencia.fila_ativacao_pico)
        self.assertEqual(0, evidencia.fila_ativacao_limite)
        self.assertEqual(["cold", "warm", "timeout", "soak-1", "soak-2", "soak-3"], [f for f, _ in chamadas])

    def test_observation_probe_falso_bloqueia_sem_inventar_sucesso(self):
        def run_once(*, timeout_s, fase):
            return {"resultado": {"inferencia_sucesso": fase != "timeout", "erro": "timeout" if fase == "timeout" else None}}

        evidencia = executar_campanha_c5(
            expected_sha="b" * 40,
            run_once=run_once,
            observation_probe=lambda: False,
            timeout_normal_s=20.0,
            timeout_probe_s=0.001,
            soak_iteracoes=1,
        )
        self.assertFalse(evidencia.observation_runtime_preservado)

    def test_soak_rejeita_zero_e_acima_do_bound(self):
        kwargs = dict(
            expected_sha="c" * 40,
            run_once=lambda **_: {},
            observation_probe=lambda: True,
            timeout_normal_s=20.0,
            timeout_probe_s=0.001,
        )
        with self.assertRaises(ValueError):
            executar_campanha_c5(**kwargs, soak_iteracoes=0)
        with self.assertRaises(ValueError):
            executar_campanha_c5(**kwargs, soak_iteracoes=65)


if __name__ == "__main__":
    unittest.main()
