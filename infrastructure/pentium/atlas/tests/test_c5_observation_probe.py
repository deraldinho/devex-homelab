import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from infrastructure.pentium.atlas.c5_observation_probe import C5ObservationProbe


class C5ObservationProbeTests(unittest.TestCase):
    def test_estado_fresco_exercita_observation_runtime_real_e_permanece_saudavel(self):
        agora = datetime(2026, 9, 6, 1, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            path.write_text(json.dumps({"schema_version": 1, "checked_at": agora.isoformat(), "status": "healthy", "checks": {}, "metrics": {}}), encoding="utf-8")
            probe = C5ObservationProbe(path, max_age_s=60, now=lambda: agora)
            self.assertTrue(probe())
            self.assertTrue(probe())
            probe.close()

    def test_estado_stale_falha_fechado(self):
        agora = datetime(2026, 9, 6, 1, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            path.write_text(json.dumps({"schema_version": 1, "checked_at": (agora - timedelta(seconds=61)).isoformat(), "status": "healthy", "checks": {}, "metrics": {}}), encoding="utf-8")
            probe = C5ObservationProbe(path, max_age_s=60, now=lambda: agora)
            self.assertFalse(probe())
            probe.close()

    def test_json_invalido_falha_fechado_sem_excecao(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            path.write_text("{", encoding="utf-8")
            probe = C5ObservationProbe(path, max_age_s=60)
            self.assertFalse(probe())
            probe.close()


if __name__ == "__main__":
    unittest.main()
