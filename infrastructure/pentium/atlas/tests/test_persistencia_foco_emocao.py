import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.contexto_foco_emocao import ContextoFocoEmocao
from infrastructure.pentium.atlas.emocao_derivada import ContextoEmocional
from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo
from infrastructure.pentium.atlas.modelo_foco import AssuntoFoco, PoliticaFoco
from infrastructure.pentium.atlas.persistencia_foco_emocao import RepositorioFocoEmocao, restaurar_foco_emocao


class PersistenciaFocoEmocaoTests(unittest.TestCase):
    def resultado(self):
        estado = EstadoAfetivo(0.2, 0.5, 0.2, 0.8, 0.7, 0.4, "2026-09-04T22:10:00+00:00")
        assunto = AssuntoFoco("core", "core", 0.8, 0.7, 0.8, 0.5, 0.7, 1.0)
        return ContextoFocoEmocao(PoliticaFoco(2, 0.15, 0.4)).processar(
            estado, (assunto,), ContextoEmocional(), "2026-09-04T22:10:01+00:00"
        )

    def test_round_trip_preserva_foco_e_emocao(self):
        with tempfile.TemporaryDirectory() as pasta:
            repo = RepositorioFocoEmocao(Path(pasta) / "a4.json")
            esperado = self.resultado()
            repo.salvar(esperado)
            atual = repo.carregar()
            self.assertEqual(esperado, atual)

    def test_ausencia_restaura_sem_inventar_emocao(self):
        with tempfile.TemporaryDirectory() as pasta:
            repo = RepositorioFocoEmocao(Path(pasta) / "ausente.json")
            resultado = restaurar_foco_emocao(repo)
            self.assertIsNone(resultado.snapshot)
            self.assertEqual("ausente", resultado.origem)

    def test_corrupcao_restaura_sem_inventar_emocao(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "corrompido.json"
            caminho.write_text("{", encoding="utf-8")
            resultado = restaurar_foco_emocao(RepositorioFocoEmocao(caminho))
            self.assertIsNone(resultado.snapshot)
            self.assertEqual("invalido", resultado.origem)
            self.assertIsNotNone(resultado.erro)


if __name__ == "__main__":
    unittest.main()
