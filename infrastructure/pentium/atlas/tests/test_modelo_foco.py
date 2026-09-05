import unittest

from infrastructure.pentium.atlas.modelo_foco import (
    AssuntoFoco,
    FocoAtencao,
    PoliticaFoco,
)


class ModeloFocoTests(unittest.TestCase):
    def assunto(self, assunto_id="core", **kwargs):
        dados = dict(
            assunto_id=assunto_id,
            entidade_id=assunto_id,
            gravidade=0.5,
            impacto_afetivo=0.4,
            importancia=0.6,
            novidade=0.3,
            urgencia=0.5,
            recencia=0.8,
        )
        dados.update(kwargs)
        return AssuntoFoco(**dados)

    def test_dimensoes_sao_limitadas(self):
        assunto = self.assunto(gravidade=2, novidade=-1)
        self.assertEqual(1.0, assunto.gravidade)
        self.assertEqual(0.0, assunto.novidade)

    def test_politica_valida_capacidade_e_margens(self):
        politica = PoliticaFoco(2, 0.15, 0.4)
        self.assertEqual(2, politica.capacidade_secundarios)
        with self.assertRaises(ValueError):
            PoliticaFoco(0, 0.15, 0.4)

    def test_foco_limita_secundarios_e_remove_principal(self):
        principal = self.assunto("firewall")
        foco = FocoAtencao(
            principal=principal,
            secundarios=(principal, self.assunto("core"), self.assunto("x99")),
            atualizado_em="2026-09-04T21:30:00+00:00",
            capacidade_secundarios=1,
        )
        self.assertEqual(("core",), tuple(x.assunto_id for x in foco.secundarios))
        self.assertEqual("2026-09-04T21:30:00+00:00", foco.atualizado_em)


if __name__ == "__main__":
    unittest.main()
