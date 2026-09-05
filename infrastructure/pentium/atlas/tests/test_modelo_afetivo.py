import unittest

from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, ImpulsoAfetivo, PersonalidadeBase


class ModeloAfetivoTests(unittest.TestCase):
    def test_estado_limita_dimensoes(self):
        estado = EstadoAfetivo(2.0, 1.5, -0.4, 1.2, -1.0, 0.6, "2026-09-04T12:00:00+00:00")
        self.assertEqual((1.0, 1.0, 0.0, 1.0, 0.0, 0.6), (
            estado.valencia, estado.ativacao, estado.estresse,
            estado.confianca, estado.engajamento, estado.curiosidade,
        ))

    def test_impulso_rejeita_delta_fora_do_intervalo(self):
        with self.assertRaises(ValueError):
            ImpulsoAfetivo("teste", delta_estresse=1.01)

    def test_personalidade_cria_estado_na_base(self):
        personalidade = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
        estado = personalidade.criar_estado("2026-09-04T12:00:00+00:00")
        self.assertEqual(0.20, estado.valencia)
        self.assertEqual(0.10, estado.estresse)
        self.assertEqual(0.75, estado.curiosidade)
        self.assertIsNone(estado.foco_atencao)

    def test_instante_com_offset_e_normalizado_para_utc(self):
        personalidade = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
        estado = personalidade.criar_estado("2026-09-04T09:00:00-03:00")
        self.assertEqual("2026-09-04T12:00:00+00:00", estado.atualizado_em)
