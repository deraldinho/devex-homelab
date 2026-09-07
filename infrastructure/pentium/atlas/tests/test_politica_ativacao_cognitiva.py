import unittest

from infrastructure.pentium.atlas.configuracao_cognitiva import PoliticaAtivacaoCognitiva
from infrastructure.pentium.atlas.modelo_contexto_cognitivo import MotivoAtivacaoCognitiva
from infrastructure.pentium.atlas.politica_ativacao_cognitiva import ActivationPolicy


class ActivationPolicyTests(unittest.TestCase):
    def politica(self, cooldown_s=120, max_budget=4):
        return ActivationPolicy(PoliticaAtivacaoCognitiva(0.75, 0.2, cooldown_s, 300, max_budget))

    def test_interacao_humana_ativa_mesmo_durante_cooldown_autonomo(self):
        politica = self.politica()
        politica.registrar_ativacao("evento-1", "2026-09-05T18:00:00+00:00", autonomo=True)
        decisao = politica.avaliar(fingerprint="humano-1", agora="2026-09-05T18:00:10+00:00", interacao_humana=True)
        self.assertTrue(decisao.ativar)
        self.assertEqual(MotivoAtivacaoCognitiva.INTERACAO_HUMANA, decisao.motivo)

    def test_evento_autonomo_equivalente_respeita_cooldown_e_budget(self):
        politica = self.politica(cooldown_s=120, max_budget=1)
        primeira = politica.avaliar(fingerprint="core:critical", agora="2026-09-05T18:00:00+00:00", criticidade=True)
        self.assertTrue(primeira.ativar)
        politica.registrar_ativacao("core:critical", "2026-09-05T18:00:00+00:00", autonomo=True)
        repetida = politica.avaliar(fingerprint="core:critical", agora="2026-09-05T18:00:30+00:00", criticidade=True)
        self.assertFalse(repetida.ativar)
        self.assertIn(repetida.razao_bloqueio, ("cooldown", "orcamento"))

    def test_novidade_e_delta_afetivo_respeitam_threshold(self):
        politica = self.politica()
        self.assertFalse(politica.avaliar(fingerprint="a", agora="2026-09-05T18:00:00+00:00", novidade=0.74).ativar)
        self.assertEqual(MotivoAtivacaoCognitiva.NOVIDADE_RELEVANTE, politica.avaliar(fingerprint="b", agora="2026-09-05T18:00:01+00:00", novidade=0.75).motivo)
        self.assertEqual(MotivoAtivacaoCognitiva.MUDANCA_AFETIVA, politica.avaliar(fingerprint="c", agora="2026-09-05T18:00:02+00:00", delta_afetivo=0.2).motivo)


if __name__ == "__main__": unittest.main()
