import unittest

from infrastructure.pentium.atlas.configuracao_cognitiva import PoliticaContextoCognitivo
from infrastructure.pentium.atlas.contexto_cognitivo import ContextoCognitivoBuilder
from infrastructure.pentium.atlas.emocao_derivada import EmocaoDerivada
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, FocoAtencao
from infrastructure.pentium.atlas.modelo_incidente import IncidenteTecnico
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.state_model import GlobalAssessment, TechnicalState
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity


class ContextoCognitivoBuilderTests(unittest.TestCase):
    def builder(self, max_string_chars=256, max_mudancas=8, max_payload=8192):
        return ContextoCognitivoBuilder(PoliticaContextoCognitivo(max_string_chars, max_mudancas, 8, 2, max_payload))

    def assessment(self):
        return GlobalAssessment(TechnicalState.DEGRADED, TechnicalState.CRITICAL, 4, ("core:offline",))

    def percepcao(self):
        return EstadoPercepcao("core", EstadoObservacao.INACESSIVEL, 0.9, None, (), ("ssh",), False, "2026-09-05T18:09:00+00:00")

    def incidente(self):
        return IncidenteTecnico("inc-1", "core", "host_unavailable", "critical", "2026-09-05T18:00:00+00:00", "core", 0.8, ("core", "l2jtoren"), 2)

    def estado(self):
        return EstadoAfetivo(-0.4, 0.9, 0.8, 0.3, 0.7, 0.8, "2026-09-05T18:09:00+00:00", "core")

    def foco(self):
        assunto = AssuntoFoco("core", "core", 1, 0.8, 1, 1, 1, 1, critico=True)
        return FocoAtencao(assunto, (), "2026-09-05T18:09:00+00:00", 2)

    def stimuli(self, quantidade):
        return tuple(Stimulus(f"s-{i}", "core", "changed", StimulusSeverity.WARNING, "2026-09-05T18:09:00+00:00", {"detail": "x" * 40, "index": i}, 0.8, "core") for i in range(quantidade))

    def test_builder_compacta_contratos_autoritativos_sem_mutar_origem(self):
        ctx = self.builder().construir(
            motivo=MotivoAtivacaoCognitiva.CRITICIDADE_TECNICA,
            assessment=self.assessment(), percepcao=self.percepcao(), incidente=self.incidente(),
            estado_afetivo=self.estado(), emocao=EmocaoDerivada("alarmado", ("vigilante",)),
            foco=self.foco(), expectativa=None, mudancas_recentes=self.stimuli(3),
            dependencias_afetadas=("l2jtoren", "database"), agora="2026-09-05T18:10:00+00:00",
        )
        self.assertEqual("critical", ctx.estado_tecnico)
        self.assertEqual("core", ctx.entidade_principal)
        self.assertEqual("alarmado", ctx.emocao_principal)
        self.assertLessEqual(ctx.payload_bytes(), 8192)
        self.assertEqual(3, len(ctx.mudancas_recentes))

    def test_builder_trunca_listas_strings_e_registra_truncamentos(self):
        ctx = self.builder(max_string_chars=12, max_mudancas=2).construir(
            motivo=MotivoAtivacaoCognitiva.NOVIDADE_RELEVANTE,
            assessment=self.assessment(), percepcao=self.percepcao(), incidente=self.incidente(),
            estado_afetivo=self.estado(), emocao=EmocaoDerivada("alarmado", ("vigilante", "curioso")),
            foco=self.foco(), expectativa=None, mudancas_recentes=self.stimuli(4),
            dependencias_afetadas=("l2jtoren", "database"), agora="2026-09-05T18:10:00+00:00",
        )
        self.assertEqual(2, len(ctx.mudancas_recentes))
        self.assertIn("mudancas_recentes", ctx.truncamentos)
        self.assertTrue(any(item.startswith("string:") for item in ctx.truncamentos))


if __name__ == "__main__":
    unittest.main()


class ContextoCognitivoMemoriaBuilderTests(ContextoCognitivoBuilderTests):
    def test_builder_inclui_memorias_relevantes(self):
        ctx = self.builder().construir(
            motivo=MotivoAtivacaoCognitiva.INTERACAO_HUMANA,
            assessment=self.assessment(), percepcao=self.percepcao(), incidente=self.incidente(),
            estado_afetivo=self.estado(), emocao=EmocaoDerivada("atento", ()),
            foco=self.foco(), expectativa=None, mudancas_recentes=(),
            dependencias_afetadas=(), agora="2026-09-05T18:10:00+00:00",
            memorias_relevantes=(
                {"memory_id": "m1", "content": "Core e membro", "importance": 0.9},
                {"memory_id": "m2", "content": "Core reiniciou", "importance": 0.7},
            ),
        )
        self.assertEqual(("m1", "m2"), tuple(item["memory_id"] for item in ctx.memorias_relevantes))

    def test_builder_inclui_contexto_expandido_grafo_preferencias_tendencias_hipoteses(self):
        ctx = self.builder().construir(
            motivo=MotivoAtivacaoCognitiva.INTERACAO_HUMANA,
            assessment=self.assessment(), percepcao=self.percepcao(), incidente=self.incidente(),
            estado_afetivo=self.estado(), emocao=EmocaoDerivada("atento", ()),
            foco=self.foco(), expectativa=None, mudancas_recentes=(),
            dependencias_afetadas=(), agora="2026-09-05T18:10:00+00:00",
            grafo_conhecimento=(
                {"entity_id": "project:l2j", "type": "project", "name": "L2jToren"},
            ),
            preferencias_operador={"active_hour": 14, "preferred_style": "direct"},
            tendencias_relevantes=(
                {"metric_key": "x99:cpu", "direction": "rising", "slope": 0.05},
            ),
            hipoteses_ativas=(
                {"hypothesis_id": "hypo-1", "title": "Memory leak no JVM", "confidence": 0.8},
            ),
        )
        self.assertEqual(1, len(ctx.grafo_conhecimento))
        self.assertEqual("project:l2j", ctx.grafo_conhecimento[0]["entity_id"])
        self.assertEqual("direct", ctx.preferencias_operador["preferred_style"])
        self.assertEqual(1, len(ctx.tendencias_relevantes))
        self.assertEqual("rising", ctx.tendencias_relevantes[0]["direction"])
        self.assertEqual(1, len(ctx.hipoteses_ativas))
        self.assertEqual("hypo-1", ctx.hipoteses_ativas[0]["hypothesis_id"])

