import json
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dashboard_collectors as dc

SHA = "e3f4723777107ee654e3ce69c40e04978000201a"
NOW = datetime(2026, 9, 8, 14, 30, tzinfo=timezone.utc)


def snapshot(generated_at: datetime = NOW) -> dict:
    return {"schema_version": 1, "generated_at": generated_at.isoformat(), "expected_sha": SHA,
            "source_stimulus_id": "stim-1", "entity_id": "x99",
            "perception": {"entidade_id": "x99", "estado": "observado", "confianca": 0.8, "conflito_evidencias": False},
            "incident": None, "affective_state": {"valencia": .2, "ativacao": .25, "estresse": .1, "confianca": .7, "engajamento": .55, "curiosidade": .75},
            "emotion": {"principal": "curioso", "nuances": ["calmo", "confiante"]},
            "focus": {"principal": {"assunto_id": "observacao:x99", "entidade_id": "x99"}},
            "recent_changes": [{"timestamp": NOW.isoformat(), "source": "x99", "kind": "status_changed", "severity": "info", "stimulus_id": "stim-1", "payload": {"secret": "no"}}],
            "affected_dependencies": []}

class DashboardCognitionTests(unittest.TestCase):
    def _cfg(self, base: Path) -> dict:
        (base / "health.json").write_text(json.dumps({"schema_version": 1, "status": "healthy", "expected_sha": SHA, "cognitive_bridge": {"current_error": None}}), encoding="utf-8")
        (base / "snapshot.json").write_text(json.dumps(snapshot()), encoding="utf-8")
        return dc.default_config() | {"cognitive_snapshot_path": str(base / "snapshot.json"), "cognitive_health_path": str(base / "health.json"), "cognitive_max_age_s": 180, "cognitive_expected_sha": SHA}

    def test_collect_cognition_available_and_sanitized(self):
        with TemporaryDirectory() as tmp:
            data = dc.collect_cognition(self._cfg(Path(tmp)), now=lambda: NOW)
        self.assertEqual(data["status"], "available")
        self.assertEqual(data["entity_id"], "x99")
        self.assertEqual(data["perception"]["confidence_percent"], 80)
        self.assertEqual(data["affective_state"]["curiosity_percent"], 75)
        self.assertNotIn("payload", data["recent_changes"][0])

    def test_collect_cognition_marks_stale_without_fallback(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp); cfg = self._cfg(base)
            (base / "snapshot.json").write_text(json.dumps(snapshot(NOW - timedelta(seconds=181))), encoding="utf-8")
            data = dc.collect_cognition(cfg, now=lambda: NOW)
        self.assertEqual(data["status"], "stale")
        self.assertNotIn("affective_state", data)

    def test_collect_cognition_unavailable_on_sha_mismatch(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp); cfg = self._cfg(base)
            bad = snapshot(); bad["expected_sha"] = "other"
            (base / "snapshot.json").write_text(json.dumps(bad), encoding="utf-8")
            data = dc.collect_cognition(cfg, now=lambda: NOW)
        self.assertEqual(data, {"status": "unavailable", "reason": "sha_mismatch"})

    def test_collect_status_exposes_cognition_group(self):
        with TemporaryDirectory() as tmp:
            cfg = self._cfg(Path(tmp))
            status = dc.collect_status(cfg, command_runner=lambda *_: dc.CommandResult(1, "", ""), cognition_now=lambda: NOW)
        self.assertEqual(status["cognition"]["status"], "available")
