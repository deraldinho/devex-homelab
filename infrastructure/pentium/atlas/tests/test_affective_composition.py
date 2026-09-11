import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.affective_composition import build_affective_composition
from infrastructure.pentium.atlas.adaptador_stimulus_percepcao import ConfigFontePercepcao
from infrastructure.pentium.atlas.grafo_dependencias import GrafoDependencias
from infrastructure.pentium.atlas.modelo_incidente import IncidenteTecnico
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.percepcao import PoliticaConfirmacaoPercepcao
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import PipelinePercepcaoCorrelacao
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-08T06:00:00+00:00"


def stim(sid, source, payload):
    return Stimulus(sid, source, "status_changed", StimulusSeverity.WARNING,
                    NOW, payload, 1.0, "corr-1")


class AffectiveCompositionTests(unittest.TestCase):
    def test_a3_restore_preserves_perception_and_active_incident(self):
        pipe = PipelinePercepcaoCorrelacao(
            {"x99": ConfigFontePercepcao("x99", "x99", ("channel_healthy",), .8)},
            PoliticaConfirmacaoPercepcao(2, .95, 8), GrafoDependencias(8),
            capacidade_evidencias_por_entidade=8, capacidade_incidentes=8,
            max_entidades_por_incidente=8, id_factory=lambda: "new-inc",
        )
        perception = EstadoPercepcao("x99", EstadoObservacao.INACESSIVEL, .8, None,
                                    (), ("x99",), False, NOW)
        incident = IncidenteTecnico("inc-old", "x99", "indisponibilidade_correlacionada",
                                    "critical", NOW, "x99", .8, ("x99",), 1)
        pipe.restaurar((perception,), (incident,))
        self.assertEqual((perception,), pipe.percepcoes())
        self.assertEqual((incident,), pipe.incidentes_ativos())

    def test_composition_ignores_wifi_and_maps_managed_x99(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = build_affective_composition(
                config_root=ROOT,
                state_dir=Path(tmp),
                now=lambda: NOW,
                id_factory=lambda: "inc-1",
            )
            ignored = comp.processar(stim("wifi-1", "wifi.presence", {"zone": "WIFI_OBSERVED"}))
            accepted = comp.processar(stim(
                "x99-1", "managed.x99",
                {"zone": "MANAGED", "channel_status": "degraded", "reads": {}},
            ))
            self.assertIsNone(ignored)
            self.assertTrue(accepted.aceito)
            self.assertEqual("x99", accepted.resultado_foco_emocao.foco.principal.entidade_id)
            self.assertIn("ignored_source:wifi.presence", comp.diagnostics())
            self.assertEqual((), comp.errors())

    def test_managed_x99_degraded_is_uncertain_not_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = build_affective_composition(config_root=ROOT, state_dir=Path(tmp),
                                                now=lambda: NOW, id_factory=lambda: "inc-1")
            result = comp.processar(stim("x99-degraded", "managed.x99",
                                         {"channel_status": "degraded", "reads": {}}))
            self.assertTrue(result.impacto.contexto_emocional.percepcao_insegura)

    def test_managed_core_degraded_enters_affective_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = build_affective_composition(config_root=ROOT, state_dir=Path(tmp),
                                                now=lambda: NOW, id_factory=lambda: "inc-core")
            result = comp.processar(stim("core-degraded", "managed.core",
                                         {"channel_status": "degraded", "reads": {}}))
            self.assertTrue(result.impacto.contexto_emocional.percepcao_insegura)

    def test_pentium_self_degraded_enters_affective_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = build_affective_composition(config_root=ROOT, state_dir=Path(tmp),
                                                now=lambda: NOW, id_factory=lambda: "inc-pentium")
            result = comp.processar(stim("pentium-degraded", "pentium.self",
                                         {"self_healthy": False, "checks": {}}))
            self.assertTrue(result.impacto.contexto_emocional.percepcao_insegura)

    def test_github_delivery_state_enters_same_affective_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = build_affective_composition(config_root=ROOT, state_dir=Path(tmp),
                                                now=lambda: NOW, id_factory=lambda: "inc-gh")
            result = comp.processar(stim(
                "gh-red", "github.deraldinho.L2jToren",
                {"repo": "deraldinho/L2jToren", "delivery_healthy": False,
                 "workflow_runs": [{"conclusion": "failure"}]},
            ))
            self.assertIsNotNone(result)
            self.assertTrue(result.aceito)
            self.assertEqual("repo:L2jToren", result.resultado_percepcao.percepcao.entidade_id)
            self.assertNotIn("ignored_source:github.deraldinho.L2jToren", comp.diagnostics())

    def test_successful_event_persists_a1_a2_a3_a4(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            comp = build_affective_composition(config_root=ROOT, state_dir=state,
                                                now=lambda: NOW, id_factory=lambda: "inc-1")
            comp.processar(stim("x99-1", "managed.x99",
                                {"channel_status": "healthy", "reads": {}}))
            for name in ("affective-state.json", "affective-context.json",
                         "perception-correlation.json", "focus-emotion.json"):
                self.assertTrue((state / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
