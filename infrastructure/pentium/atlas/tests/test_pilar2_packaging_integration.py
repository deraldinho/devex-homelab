"""Atlas 4.0 — Pilar 2: Packaging and End-to-End Integration Tests.

Valida empacotamento no instalador e o fluxo integrado completo do Pilar 2:
Propriocepção Contínua (BaselineTracker + TrendDetector + TemporalCorrelator)
conectada à construção do ContextoCognitivo com tendências operacionais.
"""
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_cognitiva import PoliticaContextoCognitivo
from infrastructure.pentium.atlas.contexto_cognitivo import ContextoCognitivoBuilder
from infrastructure.pentium.atlas.emocao_derivada import EmocaoDerivada
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, FocoAtencao
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.proprioception.baseline_tracker import (
    BaselineDeviation,
    BaselineTracker,
)
from infrastructure.pentium.atlas.proprioception.temporal_correlator import (
    TemporalCorrelation,
    TemporalCorrelator,
)
from infrastructure.pentium.atlas.proprioception.trend_detector import (
    TrendDetector,
    TrendEvent,
)
from infrastructure.pentium.atlas.state_model import GlobalAssessment, TechnicalState


class Pilar2PackagingTests(unittest.TestCase):
    def test_installer_empacota_modulos_pilar2(self):
        text = Path("infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        for filename in (
            "proprioception/__init__.py",
            "proprioception/baseline_tracker.py",
            "proprioception/trend_detector.py",
            "proprioception/temporal_correlator.py",
        ):
            self.assertIn(filename, text)
        self.assertIn("ATLAS_PROPRIOCEPTION_INSTALL_PASS", text)


class Pilar2IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.baseline_path = Path(self.tmp.name) / "baselines.json"

        self.baseline_tracker = BaselineTracker(self.baseline_path, sigma=2.0, hysteresis=3)
        self.trend_detector = TrendDetector(
            min_points=5,
            min_confidence=0.6,
            min_slope_magnitude=0.001,
            projection_hours=24.0,
            window_size=20,
            capacity_metrics={"ram_percent": (0.0, 100.0)},
        )
        self.temporal_correlator = TemporalCorrelator(
            window_seconds=300.0,
            min_cooccurrences=3,
            known_rules={tuple(sorted(["mem_pressure:pentium", "l2j_latency_spike"])): "Gargalo de memória gerando contenção de I/O"},
        )
        self.builder = ContextoCognitivoBuilder(
            PoliticaContextoCognitivo(
                max_string_chars=256,
                max_mudancas_recentes=8,
                max_dependencias_afetadas=8,
                max_nuances=3,
                max_payload_bytes=8192,
            )
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_pilar2_full_pipeline_roundtrip(self):
        # 1. Alimenta métricas normais no BaselineTracker para treinar baseline (20 amostras estáveis)
        for i in range(20):
            ts = f"2026-09-22T{10 + (i // 6):02d}:{(i % 6) * 10:02d}:00+00:00"
            val = 70.0 + (i % 3) * 0.5
            dev = self.baseline_tracker.update("pentium", "ram_percent", val, ts)
            self.assertIsNone(dev)

        stats = self.baseline_tracker.get_stats("pentium", "ram_percent")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.count, 20)
        self.assertAlmostEqual(stats.mean, 70.5, delta=1.0)

        # 2. Registra tendência de subida no TrendDetector (vazamento gradual de RAM)
        trend_event = None
        for i in range(10):
            ts = f"2026-09-22T{14 + i}:00:00+00:00"
            val = 70.0 + i * 2.5  # 70% -> 92.5%
            res = self.trend_detector.update("pentium", "ram_percent", val, ts)
            if res is not None:
                trend_event = res

        self.assertIsNotNone(trend_event)
        self.assertIsInstance(trend_event, TrendEvent)
        self.assertEqual(trend_event.direction, "rising")
        self.assertGreater(trend_event.slope, 0.0)
        self.assertGreaterEqual(trend_event.confidence, 0.6)
        # Verifica se o esgotamento para o teto de 100% foi projetado
        self.assertIsNotNone(trend_event.exhaustion_hours)
        self.assertGreater(trend_event.exhaustion_hours, 0.0)

        # 3. Detecta anomalia no BaselineTracker após atingir a histerese de 3 picos anômalos
        anomaly = None
        for i in range(3):
            ts = f"2026-09-22T17:{i * 5:02d}:00+00:00"
            dev = self.baseline_tracker.update("pentium", "ram_percent", 95.0, ts)
            if dev is not None:
                anomaly = dev

        self.assertIsNotNone(anomaly)
        self.assertIsInstance(anomaly, BaselineDeviation)
        self.assertEqual(anomaly.node, "pentium")
        self.assertEqual(anomaly.metric_key, "pentium:ram_percent")
        self.assertGreater(anomaly.z_score, 2.0)

        # 4. Registra coocorrência no TemporalCorrelator
        # Evento A: "mem_pressure:pentium" e Evento B: "l2j_latency_spike"
        correlations = []
        for i in range(4):
            t_a = f"2026-09-22T18:{i * 10:02d}:00+00:00"
            t_b = f"2026-09-22T18:{i * 10:02d}:15+00:00"
            self.temporal_correlator.record_event("mem_pressure:pentium", t_a)
            r = self.temporal_correlator.record_event("l2j_latency_spike", t_b)
            correlations.extend(r)

        self.assertGreaterEqual(len(correlations), 1)
        corr = correlations[-1]
        self.assertIsInstance(corr, TemporalCorrelation)
        self.assertIn("mem_pressure:pentium", (corr.event_a, corr.event_b))
        self.assertIn("l2j_latency_spike", (corr.event_a, corr.event_b))
        self.assertGreaterEqual(corr.confidence, 0.5)

        # Interpretação por regra pré-configurada
        interpretacao = self.temporal_correlator.get_known_interpretation("mem_pressure:pentium", "l2j_latency_spike")
        self.assertIn("Gargalo de memória", interpretacao)

        # 5. Constrói ContextoCognitivo com as tendências e anomalias proprioceptivas integradas
        assessment = GlobalAssessment(TechnicalState.BUSY, TechnicalState.HEALTHY, 1, ())
        percepcao = EstadoPercepcao("node:pentium", EstadoObservacao.OBSERVADO, 0.98, None, (), (), False, "2026-09-22T19:00:00+00:00")
        estado_afetivo = EstadoAfetivo(0.1, 0.6, 0.4, 0.8, 0.7, 0.5, "2026-09-22T19:00:00+00:00", "node:pentium")
        foco = FocoAtencao(AssuntoFoco("node:pentium", "node:pentium", 1, 0.8, 1, 1, 1, 1), (), "2026-09-22T19:00:00+00:00", 1)

        tendencias_payload = (
            {
                "metrica": trend_event.metric_key,
                "direcao": trend_event.direction,
                "inclinacao": round(trend_event.slope, 4),
                "confianca": round(trend_event.confidence, 4),
                "horas_para_esgotamento": round(trend_event.exhaustion_hours, 1) if trend_event.exhaustion_hours else None,
                "z_score_atual": round(anomaly.z_score, 2),
                "correlacao_causal": "l2j_latency_spike",
                "interpretacao_diagnostica": interpretacao,
            },
        )

        ctx = self.builder.construir(
            motivo=MotivoAtivacaoCognitiva.MUDANCA_ESTADO,
            assessment=assessment,
            percepcao=percepcao,
            incidente=None,
            estado_afetivo=estado_afetivo,
            emocao=EmocaoDerivada("atento", ("vigilante",)),
            foco=foco,
            expectativa=None,
            mudancas_recentes=(),
            dependencias_afetadas=("node:x99", "proj:l2jtoren"),
            agora="2026-09-22T19:00:00+00:00",
            tendencias_relevantes=tendencias_payload,
        )

        # Validações do ContextoCognitivo com propriocepção
        self.assertEqual(ctx.entidade_principal, "node:pentium")
        self.assertEqual(ctx.emocao_principal, "atento")
        self.assertEqual(len(ctx.tendencias_relevantes), 1)
        self.assertEqual(ctx.tendencias_relevantes[0]["metrica"], "pentium:ram_percent")
        self.assertEqual(ctx.tendencias_relevantes[0]["direcao"], "rising")
        self.assertEqual(ctx.tendencias_relevantes[0]["correlacao_causal"], "l2j_latency_spike")
        self.assertIn("Gargalo de memória", ctx.tendencias_relevantes[0]["interpretacao_diagnostica"])
        self.assertLessEqual(ctx.payload_bytes(), 8192)


if __name__ == "__main__":
    unittest.main()
