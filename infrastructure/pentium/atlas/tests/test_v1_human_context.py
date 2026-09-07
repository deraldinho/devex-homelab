import json, tempfile, unittest
from pathlib import Path
from datetime import datetime, timezone

from infrastructure.pentium.atlas.human_context import HumanContextProvider


class HumanContextProviderTests(unittest.TestCase):
    def test_healthy_heartbeat_becomes_observed_neutral_context(self):
        now = datetime(2026, 9, 6, 23, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            path.write_text(json.dumps({"schema_version": 1, "checked_at": now.isoformat(), "status": "healthy"}), encoding="utf-8")
            ctx = HumanContextProvider(path, now=lambda: now)()
        self.assertEqual("healthy", ctx["assessment"].state.value)
        self.assertEqual("observado", ctx["percepcao"].estado.value)
        self.assertEqual("calmo", ctx["emocao"].principal)
        self.assertEqual([], ctx["mudancas_recentes"])

    def test_missing_health_file_fails_closed_as_degraded_unknown(self):
        now = datetime(2026, 9, 6, 23, 30, tzinfo=timezone.utc)
        ctx = HumanContextProvider(Path("Z:/missing/latest.json"), now=lambda: now)()
        self.assertEqual("degraded", ctx["assessment"].state.value)
        self.assertEqual("desconhecido", ctx["percepcao"].estado.value)


if __name__ == "__main__": unittest.main()
