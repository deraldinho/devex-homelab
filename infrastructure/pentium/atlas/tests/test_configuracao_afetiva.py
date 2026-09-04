import json
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.configuracao_afetiva import carregar_configuracao_afetiva


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "infrastructure" / "pentium" / "atlas" / "config_afetiva.json"


class ConfiguracaoAfetivaTests(unittest.TestCase):
    def test_configuracao_do_repositorio_carrega_valores_canonicos(self):
        cfg = carregar_configuracao_afetiva(CONFIG)
        self.assertEqual(0.20, cfg.personalidade.valencia)
        self.assertEqual(0.10, cfg.personalidade.estresse)
        self.assertEqual(0.75, cfg.personalidade.curiosidade)
        self.assertEqual(900.0, cfg.decaimento.meia_vida_ativacao_s)
        self.assertEqual(3600.0, cfg.decaimento.atenuacao_offline_maxima_s)

    def test_versao_de_esquema_diferente_de_um_e_rejeitada(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"versao_esquema": 2}), encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_configuracao_afetiva(path)

    def test_meia_vida_nao_positiva_e_rejeitada(self):
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        payload["decaimento"]["meia_vida_ativacao_s"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                carregar_configuracao_afetiva(path)
