import unittest

from infrastructure.pentium.atlas.contexto_afetivo import ContextoAfetivo
from infrastructure.pentium.atlas.modelo_contexto_afetivo import (
    EntidadeAfetiva,
    Expectativa,
    ExperienciaOperacional,
    TipoEntidadeAfetiva,
    TipoExpectativa,
    TipoExperienciaOperacional,
    VinculoAfetivo,
)


class ContextoAfetivoTests(unittest.TestCase):
    def test_membro_so_tem_vinculo_efetivo_depois_de_incorporado(self):
        contexto = ContextoAfetivo(capacidade_historico=4)
        contexto.cadastrar_entidade(EntidadeAfetiva("core", "Core", TipoEntidadeAfetiva.MEMBRO))
        contexto.definir_vinculo(VinculoAfetivo("core", 0.8, 0.8, 0.9, 0.7, 0.4, 0.6))
        self.assertIsNone(contexto.vinculo_efetivo("core"))
        contexto.incorporar_membro("core")
        contexto.incorporar_membro("core")
        self.assertEqual("core", contexto.vinculo_efetivo("core").entidade_id)

    def test_expectativa_e_avaliada_sem_consultar_saude_tecnica(self):
        contexto = ContextoAfetivo(capacidade_historico=4)
        contexto.cadastrar_entidade(EntidadeAfetiva("x99", "x99", TipoEntidadeAfetiva.MEMBRO))
        contexto.adicionar_expectativa(Expectativa(
            "retorno-x99", "x99", TipoExpectativa.RETORNO_ESPERADO,
            "2026-09-04T12:00:00+00:00", "2026-09-04T13:00:00+00:00",
            "2026-09-04T14:00:00+00:00",
        ))
        self.assertEqual("atrasada", contexto.estado_expectativa(
            "retorno-x99", "2026-09-04T14:00:01+00:00"
        ).value)

    def test_historico_e_bounded_e_evento_duplicado_e_idempotente(self):
        contexto = ContextoAfetivo(capacidade_historico=2)
        contexto.cadastrar_entidade(EntidadeAfetiva("core", "Core", TipoEntidadeAfetiva.MEMBRO))
        for numero in range(3):
            self.assertTrue(contexto.registrar_experiencia(ExperienciaOperacional(
                f"inc-{numero}", "core", TipoExperienciaOperacional.INCIDENTE,
                f"2026-09-04T12:0{numero}:00+00:00",
            )))
        self.assertEqual(["inc-1", "inc-2"], [e.experiencia_id for e in contexto.historico_de("core")])
        self.assertFalse(contexto.registrar_experiencia(ExperienciaOperacional(
            "inc-2", "core", TipoExperienciaOperacional.INCIDENTE,
            "2026-09-04T12:02:00+00:00",
        )))

    def test_fator_reincidencia_conta_repeticoes_na_janela(self):
        contexto = ContextoAfetivo(capacidade_historico=5)
        contexto.cadastrar_entidade(EntidadeAfetiva("core", "Core", TipoEntidadeAfetiva.MEMBRO))
        for numero, minuto in enumerate((0, 10, 20)):
            contexto.registrar_experiencia(ExperienciaOperacional(
                f"evt-{numero}", "core", TipoExperienciaOperacional.INCIDENTE,
                f"2026-09-04T12:{minuto:02d}:00+00:00",
            ))
        fator = contexto.fator_reincidencia(
            "core", "2026-09-04T12:30:00+00:00",
            janela_s=3600, limite_repeticoes=2,
        )
        self.assertEqual(1.0, fator)

    def test_vinculo_exige_entidade_cadastrada(self):
        contexto = ContextoAfetivo(capacidade_historico=2)
        with self.assertRaises(KeyError):
            contexto.definir_vinculo(VinculoAfetivo("fantasma", 1, 1, 1, 1, 1, 1))
