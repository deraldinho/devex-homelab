import unittest

from infrastructure.pentium.atlas.correlacionador_incidentes import CorrelacionadorIncidentes
from infrastructure.pentium.atlas.grafo_dependencias import GrafoDependencias
from infrastructure.pentium.atlas.modelo_incidente import EstadoRecuperacaoIncidente
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao


def percepcao(entidade, estado):
    return EstadoPercepcao(
        entidade, estado, 0.9, None, (), (), False,
        "2026-09-04T12:00:00+00:00",
    )


class CorrelacionadorIncidentesTests(unittest.TestCase):
    def setUp(self):
        self.grafo = GrafoDependencias(32)
        self.grafo.adicionar_dependencia("modem", "internet")
        self.grafo.adicionar_dependencia("firewall", "modem")
        self.grafo.adicionar_dependencia("core", "firewall")
        self.grafo.adicionar_dependencia("x99", "firewall")
        self.grafo.adicionar_dependencia("l2jtoren", "core")
        self.correl = CorrelacionadorIncidentes(self.grafo, capacidade_incidentes=8, max_entidades_por_incidente=4, id_factory=lambda: "inc-1")

    def test_firewall_e_membros_viram_um_incidente_principal(self):
        estados = {
            "firewall": percepcao("firewall", EstadoObservacao.INACESSIVEL),
            "core": percepcao("core", EstadoObservacao.INACESSIVEL),
            "x99": percepcao("x99", EstadoObservacao.INACESSIVEL),
        }
        incidentes = self.correl.atualizar(estados, "2026-09-04T12:00:00+00:00")
        self.assertEqual(1, len(incidentes))
        self.assertEqual("firewall", incidentes[0].entidade_principal)
        self.assertEqual(("core", "firewall", "x99"), incidentes[0].entidades_afetadas)

    def test_internet_externa_e_causa_quando_resto_observado(self):
        estados = {
            "internet": percepcao("internet", EstadoObservacao.INACESSIVEL),
            "firewall": percepcao("firewall", EstadoObservacao.OBSERVADO),
            "core": percepcao("core", EstadoObservacao.OBSERVADO),
            "x99": percepcao("x99", EstadoObservacao.OBSERVADO),
        }
        incidentes = self.correl.atualizar(estados, "2026-09-04T12:00:00+00:00")
        self.assertEqual("internet", incidentes[0].entidade_principal)

    def test_tempestade_trunca_lista_mas_preserva_total(self):
        grafo = GrafoDependencias(32)
        for nome in ("p1", "p2", "p3", "p4", "p5"):
            grafo.adicionar_dependencia(nome, "core")
        correl = CorrelacionadorIncidentes(grafo, capacidade_incidentes=4, max_entidades_por_incidente=3, id_factory=lambda: "inc-storm")
        estados = {"core": percepcao("core", EstadoObservacao.INACESSIVEL)}
        estados.update({nome: percepcao(nome, EstadoObservacao.INACESSIVEL) for nome in ("p1", "p2", "p3", "p4", "p5")})
        incidente = correl.atualizar(estados, "2026-09-04T12:00:00+00:00")[0]
        self.assertEqual(6, incidente.total_entidades_afetadas)
        self.assertEqual(3, len(incidente.entidades_afetadas))

    def test_recuperacao_do_root_encerra_incidente(self):
        estados = {"firewall": percepcao("firewall", EstadoObservacao.INACESSIVEL)}
        incidente = self.correl.atualizar(estados, "2026-09-04T12:00:00+00:00")[0]
        recuperado = {"firewall": percepcao("firewall", EstadoObservacao.OBSERVADO)}
        encerrado = self.correl.atualizar(recuperado, "2026-09-04T12:10:00+00:00")[0]
        self.assertEqual(incidente.incidente_id, encerrado.incidente_id)
        self.assertEqual(EstadoRecuperacaoIncidente.RECUPERADO, encerrado.estado_recuperacao)


if __name__ == "__main__":
    unittest.main()
