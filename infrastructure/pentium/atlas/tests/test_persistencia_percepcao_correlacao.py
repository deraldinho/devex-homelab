import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.modelo_incidente import IncidenteTecnico
from infrastructure.pentium.atlas.modelo_percepcao import EstadoObservacao, EstadoPercepcao
from infrastructure.pentium.atlas.persistencia_percepcao_correlacao import (
    OrigemRestauracaoPercepcaoCorrelacao,
    RepositorioPercepcaoCorrelacao,
)


def estado():
    return EstadoPercepcao(
        "core", EstadoObservacao.INACESSIVEL, 0.9, None,
        (), ("ping", "ssh"), False, "2026-09-04T12:00:00+00:00",
    )


def incidente():
    return IncidenteTecnico(
        "inc-1", "core", "indisponibilidade_correlacionada", "critical",
        "2026-09-04T12:00:00+00:00", "core", 1.0, ("core",), 1,
    )


class PersistenciaPercepcaoCorrelacaoTests(unittest.TestCase):
    def test_round_trip_preserva_percepcao_e_incidente(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioPercepcaoCorrelacao(Path(tmp) / "a3.json")
            repo.salvar((estado(),), (incidente(),))
            resultado = repo.restaurar()
            self.assertEqual(OrigemRestauracaoPercepcaoCorrelacao.ESTADO_SALVO, resultado.origem)
            self.assertEqual((estado(),), resultado.percepcoes)
            self.assertEqual((incidente(),), resultado.incidentes)

    def test_arquivo_ausente_restaura_vazio_sem_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            resultado = RepositorioPercepcaoCorrelacao(Path(tmp) / "a3.json").restaurar()
            self.assertEqual(OrigemRestauracaoPercepcaoCorrelacao.BASE_POR_AUSENCIA, resultado.origem)
            self.assertEqual((), resultado.percepcoes)
            self.assertIsNone(resultado.erro)

    def test_corrupcao_restaura_vazio_com_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a3.json"
            path.write_text("{quebrado", encoding="utf-8")
            resultado = RepositorioPercepcaoCorrelacao(path).restaurar()
            self.assertEqual(OrigemRestauracaoPercepcaoCorrelacao.BASE_POR_ESTADO_INVALIDO, resultado.origem)
            self.assertEqual((), resultado.incidentes)
            self.assertIsNotNone(resultado.erro)

    def test_esquema_incompativel_e_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a3.json"
            path.write_text(json.dumps({"versao_esquema": 2}), encoding="utf-8")
            resultado = RepositorioPercepcaoCorrelacao(path).restaurar()
            self.assertEqual(OrigemRestauracaoPercepcaoCorrelacao.BASE_POR_ESTADO_INVALIDO, resultado.origem)


if __name__ == "__main__":
    unittest.main()
