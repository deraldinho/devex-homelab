import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoVisualAtlas
from infrastructure.pentium.atlas.visual_state_publisher import VisualStatePublisher

class VisualStatePublisherTests(unittest.TestCase):
    def estado(self):
        return EstadoVisualAtlas(
            modo="OBSERVANDO", expressao="ATENTO", intensidade_expressao=.5,
            foco_visual="core", direcao_olhar="core", gesto_atual="nenhum",
            velocidade_movimento=.4, intensidade_movimento=.4,
            falando=False, ouvindo=False, pensando=False, duvida_identidade=False,
            transicao_ms=400,
        )

    def test_publica_json_atomico_versionado_com_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "visual-state.json"
            VisualStatePublisher(path).publicar(self.estado())
            raw = path.read_bytes()
            self.assertTrue(raw.endswith(b"\n"))
            payload = json.loads(raw.decode("utf-8"))
            self.assertEqual(1, payload["versao_avatar"])
            self.assertEqual("ATENTO", payload["expressao"])
            self.assertFalse(path.with_name(path.name + ".tmp").exists())

    def test_falha_no_replace_remove_temporario(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "visual-state.json"
            publisher = VisualStatePublisher(path)
            with patch.object(os, "replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    publisher.publicar(self.estado())
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
            self.assertFalse(path.exists())

if __name__ == "__main__":
    unittest.main()
