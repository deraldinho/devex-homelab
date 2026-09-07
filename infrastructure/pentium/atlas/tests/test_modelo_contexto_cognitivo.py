import unittest

from infrastructure.pentium.atlas.modelo_contexto_cognitivo import (
    ContextoCognitivo,
    MotivoAtivacaoCognitiva,
)


class ModeloContextoCognitivoTests(unittest.TestCase):
    def test_contexto_normaliza_timestamp_e_serializa_deterministicamente(self):
        ctx = ContextoCognitivo(
            versao_schema=1,
            timestamp="2026-09-05T15:00:00-03:00",
            motivo_ativacao=MotivoAtivacaoCognitiva.INTERACAO_HUMANA,
            entidade_principal="core",
            estado_tecnico="healthy",
            estado_percepcao="observado",
            incidente_principal=None,
            estado_afetivo={"valencia": 0.1, "foco_atencao": "core"},
            emocao_principal="calmo",
            nuances=("confiante",),
            foco_atencao="core",
            expectativa=None,
            mudancas_recentes=(),
            dependencias_afetadas=(),
            truncamentos=(),
        )
        self.assertEqual("2026-09-05T18:00:00+00:00", ctx.timestamp)
        self.assertEqual(ctx.to_dict(), ctx.to_dict())
        self.assertGreater(ctx.payload_bytes(), 0)


if __name__ == "__main__":
    unittest.main()


class ModeloContextoMemoriaTests(unittest.TestCase):
    def test_contexto_serializa_memorias_relevantes_bounded(self):
        ctx = ContextoCognitivo(
            versao_schema=1,
            timestamp="2026-09-05T18:00:00+00:00",
            motivo_ativacao=MotivoAtivacaoCognitiva.INTERACAO_HUMANA,
            entidade_principal="core",
            estado_tecnico="healthy",
            estado_percepcao="observado",
            incidente_principal=None,
            estado_afetivo={"valencia": 0.2},
            emocao_principal="calmo",
            nuances=(), foco_atencao=None, expectativa=None,
            mudancas_recentes=(), dependencias_afetadas=(), truncamentos=(),
            memorias_relevantes=({"memory_id": "m1", "content": "Core e membro"},),
        )
        self.assertEqual("m1", ctx.to_dict()["memorias_relevantes"][0]["memory_id"])
