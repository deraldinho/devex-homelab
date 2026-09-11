import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dashboard_collectors as dc


class ContinuousIntentCollectorTests(unittest.TestCase):
    def test_missing_intent_file_returns_unavailable(self):
        cfg = dc.default_config() | {"continuous_intent_path": "Z:/missing/continuous-intent.json"}
        result = dc.collect_continuous_intent(cfg)
        self.assertEqual({"status": "unavailable", "intent": None}, result)

    def test_valid_intent_is_sanitized_and_bounded(self):
        payload = {
            "schema_version": 1,
            "communication_mode": "silent_tracking",
            "material_fingerprint": "f" * 400,
            "intent": {
                "intencao_id": "intent-1", "tipo": "ACOMPANHAR_RECUPERACAO",
                "estado": "ATIVA", "assunto_id": "core", "entidade_id": "core",
                "motivo": "degraded", "prioridade": .82,
                "iniciado_em": "2026-09-11T21:00:00+00:00",
                "atualizado_em": "2026-09-11T21:01:00+00:00",
                "valido_ate": "2026-09-11T21:05:00+00:00",
                "notificado_usuario": True, "episodio_id": None,
                "unexpected": "secret",
            },
        }
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "continuous-intent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = dc.collect_continuous_intent(dc.default_config() | {"continuous_intent_path": str(path)})
        self.assertEqual("available", result["status"])
        self.assertEqual("silent_tracking", result["communication_mode"])
        self.assertEqual("ATIVA", result["intent"]["estado"])
        self.assertEqual("core", result["intent"]["assunto_id"])
        self.assertNotIn("unexpected", result["intent"])
        self.assertLessEqual(len(result["material_fingerprint"]), 256)

    def test_collect_status_exposes_continuous_intent_group(self):
        status = dc.collect_status(
            dc.default_config(),
            command_runner=lambda *_: dc.CommandResult(1, "", ""),
        )
        self.assertIn("continuous_intent", status)


class ContinuousIntentUiTests(unittest.TestCase):
    def test_ui_renders_continuous_intent_status(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        for token in (
            "continuousIntentState", "continuousIntentSubject", "continuousIntentMode",
            "continuousIntentDuration", "renderContinuousIntent", "status.continuous_intent",
            "ACOMPANHANDO", "AGUARDANDO VOCÊ", "RECUPERADO",
        ):
            self.assertIn(token, html)

    def test_avatar_renderer_accepts_intent_projection_without_mutating_visual_contract(self):
        renderer = (ROOT / "atlas-avatar-renderer.js").read_text(encoding="utf-8")
        self.assertIn("function renderIntent", renderer)
        self.assertIn("window.AtlasAvatarRenderer", renderer)
        self.assertIn("intentHeadline", renderer)


if __name__ == "__main__":
    unittest.main()
