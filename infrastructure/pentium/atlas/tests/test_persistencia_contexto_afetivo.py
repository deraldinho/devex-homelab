import json
import tempfile
import unittest
from pathlib import Path

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
from infrastructure.pentium.atlas.persistencia_contexto_afetivo import (
    OrigemRestauracaoContexto,
    RepositorioContextoAfetivo,
    restaurar_contexto,
)


class PersistenciaContextoAfetivoTests(unittest.TestCase):
    def _contexto(self):
        contexto = ContextoAfetivo(2)
        contexto.cadastrar_entidade(EntidadeAfetiva("core", "Core", TipoEntidadeAfetiva.MEMBRO))
        contexto.incorporar_membro("core")
        contexto.definir_vinculo(VinculoAfetivo("core", .8, .7, .9, .6, .4, .5))
        contexto.adicionar_expectativa(Expectativa(
            "exp-core", "core", TipoExpectativa.RETORNO_ESPERADO,
            "2026-09-04T12:00:00+00:00", "2026-09-04T13:00:00+00:00",
            "2026-09-04T14:00:00+00:00",
        ))
        for indice in range(3):
            contexto.registrar_experiencia(ExperienciaOperacional(
                f"evt-{indice}", "core", TipoExperienciaOperacional.INCIDENTE,
                f"2026-09-04T12:0{indice}:00+00:00",
            ))
        return contexto

    def test_round_trip_preserva_contexto_e_limite(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioContextoAfetivo(Path(tmp) / "contexto.json", 2)
            repo.salvar(self._contexto())
            restaurado = repo.carregar()
            self.assertEqual(2, restaurado.capacidade_historico)
            self.assertTrue(restaurado.entidades()[0].incorporada)
            self.assertEqual("core", restaurado.vinculos()[0].entidade_id)
            self.assertEqual("exp-core", restaurado.expectativas()[0].expectativa_id)
            self.assertEqual(["evt-1", "evt-2"], [e.experiencia_id for e in restaurado.historico_de("core")])

    def test_ausencia_restaura_contexto_vazio_sem_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioContextoAfetivo(Path(tmp) / "contexto.json", 3)
            resultado = restaurar_contexto(repo)
            self.assertEqual(OrigemRestauracaoContexto.VAZIO_POR_AUSENCIA, resultado.origem)
            self.assertEqual(3, resultado.contexto.capacidade_historico)
            self.assertEqual((), resultado.contexto.entidades())
            self.assertIsNone(resultado.erro)

    def test_corrupcao_restaura_contexto_vazio_com_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contexto.json"
            path.write_text("{quebrado", encoding="utf-8")
            resultado = restaurar_contexto(RepositorioContextoAfetivo(path, 2))
            self.assertEqual(OrigemRestauracaoContexto.VAZIO_POR_ESTADO_INVALIDO, resultado.origem)
            self.assertEqual((), resultado.contexto.entidades())
            self.assertIsNotNone(resultado.erro)

    def test_esquema_incompativel_e_estado_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contexto.json"
            path.write_text(json.dumps({"versao_esquema": 2}), encoding="utf-8")
            resultado = restaurar_contexto(RepositorioContextoAfetivo(path, 2))
            self.assertEqual(OrigemRestauracaoContexto.VAZIO_POR_ESTADO_INVALIDO, resultado.origem)
