import itertools
import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.adaptador_impacto_afetivo import AdaptadorImpactoAfetivo, ConfigImpactoAfetivo
from infrastructure.pentium.atlas.adaptador_stimulus_percepcao import ConfigFontePercepcao
from infrastructure.pentium.atlas.affective_runtime import AffectiveRuntime
from infrastructure.pentium.atlas.compositor_visual_afetivo import CompositorVisualAfetivo
from infrastructure.pentium.atlas.contexto_afetivo import ContextoAfetivo
from infrastructure.pentium.atlas.contexto_foco_emocao import ContextoFocoEmocao
from infrastructure.pentium.atlas.grafo_dependencias import GrafoDependencias
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento
from infrastructure.pentium.atlas.modelo_contexto_afetivo import EntidadeAfetiva, TipoEntidadeAfetiva, VinculoAfetivo
from infrastructure.pentium.atlas.modelo_foco import PoliticaFoco
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoInteracaoVisual
from infrastructure.pentium.atlas.motor_afetivo import MotorEstadoAfetivo
from infrastructure.pentium.atlas.observation_runtime import ObservationRuntime
from infrastructure.pentium.atlas.percepcao import PoliticaConfirmacaoPercepcao
from infrastructure.pentium.atlas.pipeline_afetivo_observacional import PipelineAfetivoObservacional, carregar_config_observation_affective
from infrastructure.pentium.atlas.pipeline_percepcao_correlacao import PipelinePercepcaoCorrelacao
from infrastructure.pentium.atlas.stimulus_bus import StimulusBus
from infrastructure.pentium.atlas.stimulus_model import StimulusSeverity
from infrastructure.pentium.atlas.stimulus_sources import SourceSnapshot
from infrastructure.pentium.atlas.visual_state_publisher import VisualStatePublisher

NOW = "2026-09-08T03:00:00+00:00"
ROOT = Path(__file__).resolve().parents[4]
ATLAS = ROOT / "infrastructure" / "pentium" / "atlas"


class OneShotSource:
    def __init__(self, name):
        self.name = name
    def poll(self):
        return SourceSnapshot(
            self.name,
            "degraded",
            StimulusSeverity.WARNING,
            {"reachable": False},
            NOW,
        )


class ObservationAffectiveIntegrationTests(unittest.TestCase):
    def test_observation_reaches_real_visual_snapshot_after_a3_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "visual-state.json"
            personalidade = PersonalidadeBase(0.2, 0.25, 0.1, 0.7, 0.55, 0.75)
            politica_decaimento = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)
            motor = MotorEstadoAfetivo(
                personalidade,
                politica_decaimento,
                personalidade.criar_estado(NOW),
                lambda: NOW,
            )
            contexto_a2 = ContextoAfetivo(capacidade_historico=16)
            contexto_a2.cadastrar_entidade(
                EntidadeAfetiva("core", "Core", TipoEntidadeAfetiva.ORGAO_VITAL)
            )
            contexto_a2.definir_vinculo(
                VinculoAfetivo("core", 1.0, 1.0, 1.0, 1.0, 0.8, 0.9)
            )
            grafo = GrafoDependencias(8)
            configs = {
                "core.agent": ConfigFontePercepcao("core.agent", "core", ("reachable",), 0.8),
                "core.ping": ConfigFontePercepcao("core.ping", "core", ("reachable",), 0.8),
            }
            pipeline_a3 = PipelinePercepcaoCorrelacao(
                configs,
                PoliticaConfirmacaoPercepcao(2, 0.95, 8),
                grafo,
                capacidade_evidencias_por_entidade=8,
                capacidade_incidentes=8,
                max_entidades_por_incidente=8,
                id_factory=lambda: "inc-1",
            )
            contexto_a4 = ContextoFocoEmocao(
                PoliticaFoco(3, 0.15, 0.4),
                capacidade_nuances=2,
            )
            visual_runtime = AffectiveRuntime(
                CompositorVisualAfetivo(),
                VisualStatePublisher(path),
                interacao_inicial=EstadoInteracaoVisual(atualizado_em=NOW),
            )
            cfg = carregar_config_observation_affective(ATLAS / "config_observation_affective.json")
            pipeline = PipelineAfetivoObservacional(
                pipeline_percepcao=pipeline_a3,
                contexto_afetivo=contexto_a2,
                adaptador=AdaptadorImpactoAfetivo(cfg.impacto),
                motor_afetivo=motor,
                contexto_foco_emocao=contexto_a4,
                affective_runtime=visual_runtime,
                capacidade_stimulus_ids=cfg.capacidade_stimulus_ids,
                capacidade_incidentes=cfg.capacidade_incidentes,
                capacidade_assuntos=cfg.capacidade_assuntos,
                capacidade_erros=cfg.capacidade_erros,
                janela_reincidencia_s=cfg.janela_reincidencia_s,
                limite_repeticoes=cfg.limite_repeticoes,
            )
            ids = itertools.count()
            bus = StimulusBus(capacity=16)
            journaled = []
            observation = ObservationRuntime(
                sources=[OneShotSource("core.agent"), OneShotSource("core.ping")],
                bus=bus,
                journal=lambda item: journaled.append(item.stimulus_id),
                id_factory=lambda: f"obs-{next(ids)}",
                poll_runner=lambda source, timeout: source.poll(),
                accepted_stimulus_sink=pipeline.processar,
            )

            first = observation.run_once("core.agent")
            interim = json.loads(path.read_text(encoding="utf-8"))
            second = observation.run_once("core.ping")
            final = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual("baseline_observed", first.kind)
            self.assertEqual("baseline_observed", second.kind)
            self.assertEqual(2, len(journaled))
            self.assertEqual("OBSERVANDO", interim["modo"])
            self.assertEqual("REAGINDO", final["modo"])
            self.assertEqual("SOB_PRESSAO", final["expressao"])
            self.assertEqual("core", final["foco_visual"])
            self.assertIsNone(motor.estado_atual.foco_atencao)
            self.assertEqual((), pipeline.errors())
            self.assertEqual((), observation.errors())


if __name__ == "__main__":
    unittest.main()
