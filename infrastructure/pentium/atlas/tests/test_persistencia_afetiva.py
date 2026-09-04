import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.modelo_afetivo import EstadoAfetivo, PersonalidadeBase, PoliticaDecaimento
from infrastructure.pentium.atlas.persistencia_afetiva import OrigemRestauracaoAfetiva, RepositorioEstadoAfetivo, restaurar_estado


P = PersonalidadeBase(0.20, 0.25, 0.10, 0.70, 0.55, 0.75)
D = PoliticaDecaimento(3600, 900, 1800, 21600, 7200, 10800, 3600)


class PersistenciaAfetivaTests(unittest.TestCase):
    def test_salvar_e_carregar_preserva_estado(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioEstadoAfetivo(Path(tmp) / "estado.json")
            estado = EstadoAfetivo(0.40, 0.60, 0.80, 0.50, 0.70, 0.90, "2026-09-04T12:00:00+00:00", "core")
            repo.salvar(estado)
            self.assertEqual(estado, repo.carregar())
            self.assertFalse((Path(tmp) / "estado.json.tmp").exists())

    def test_arquivo_corrompido_retorna_base_com_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "estado.json"
            path.write_text("{quebrado", encoding="utf-8")
            resultado = restaurar_estado(RepositorioEstadoAfetivo(path), P, D, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.BASE_POR_ESTADO_INVALIDO, resultado.origem)
            self.assertIsNotNone(resultado.erro)

    def test_arquivo_ausente_retorna_base_sem_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            resultado = restaurar_estado(RepositorioEstadoAfetivo(Path(tmp) / "estado.json"), P, D, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.BASE_POR_AUSENCIA, resultado.origem)
            self.assertIsNone(resultado.erro)

    def test_restauracao_limita_atenuacao_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = RepositorioEstadoAfetivo(Path(tmp) / "estado.json")
            repo.salvar(EstadoAfetivo(0.80, 0.25, 0.10, 0.70, 0.55, 0.75, "2026-09-04T00:00:00+00:00"))
            resultado = restaurar_estado(repo, P, D, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.ESTADO_SALVO, resultado.origem)
            self.assertAlmostEqual(0.50, resultado.estado.valencia, places=9)

    def test_timestamp_futuro_do_estado_salvo_nao_bloqueia_retomada(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "estado.json"
            path.write_text(json.dumps({
                "versao_esquema": 1,
                "estado": {
                    "valencia": 0.8, "ativacao": 0.25, "estresse": 0.1,
                    "confianca": 0.7, "engajamento": 0.55, "curiosidade": 0.75,
                    "atualizado_em": "2026-09-05T12:00:00+00:00", "foco_atencao": None,
                },
            }), encoding="utf-8")
            resultado = restaurar_estado(RepositorioEstadoAfetivo(path), P, D, "2026-09-04T12:00:00+00:00")
            self.assertEqual(OrigemRestauracaoAfetiva.BASE_POR_ESTADO_INVALIDO, resultado.origem)
            self.assertIsNotNone(resultado.erro)
