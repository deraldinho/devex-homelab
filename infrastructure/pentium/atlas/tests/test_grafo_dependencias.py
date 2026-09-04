import unittest

from infrastructure.pentium.atlas.grafo_dependencias import GrafoDependencias


class GrafoDependenciasTests(unittest.TestCase):
    def test_aresta_duplicada_e_idempotente(self):
        grafo = GrafoDependencias(8)
        grafo.adicionar_dependencia("core", "firewall")
        grafo.adicionar_dependencia("core", "firewall")
        self.assertEqual(("firewall",), grafo.dependencias_de("core"))

    def test_self_loop_e_rejeitado(self):
        grafo = GrafoDependencias(8)
        with self.assertRaises(ValueError):
            grafo.adicionar_dependencia("core", "core")

    def test_ciclo_e_rejeitado(self):
        grafo = GrafoDependencias(8)
        grafo.adicionar_dependencia("core", "firewall")
        with self.assertRaises(ValueError):
            grafo.adicionar_dependencia("firewall", "core")

    def test_dependentes_transitivos_sao_deterministicos(self):
        grafo = GrafoDependencias(8)
        grafo.adicionar_dependencia("core", "firewall")
        grafo.adicionar_dependencia("l2jtoren", "core")
        grafo.adicionar_dependencia("x99", "firewall")
        self.assertEqual(("core", "l2jtoren", "x99"), grafo.dependentes_transitivos("firewall"))

    def test_capacidade_maxima_e_respeitada(self):
        grafo = GrafoDependencias(2)
        grafo.adicionar_dependencia("core", "firewall")
        grafo.adicionar_dependencia("x99", "firewall")
        with self.assertRaises(OverflowError):
            grafo.adicionar_dependencia("l2jtoren", "core")


if __name__ == "__main__":
    unittest.main()
