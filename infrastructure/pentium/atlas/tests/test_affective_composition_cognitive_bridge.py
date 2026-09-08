import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.affective_composition import build_affective_composition
from infrastructure.pentium.atlas.tests.test_affective_composition import ROOT, NOW, stim


class RecordingPublisher:
    def __init__(self, state_dir, *, fail_first=False):
        self.state_dir = Path(state_dir)
        self.fail_first = fail_first
        self.calls = []

    def publish(self, stimulus, perception_result, impact, focus_result, recent_changes):
        self.calls.append((stimulus, perception_result, impact, focus_result, tuple(recent_changes)))
        if self.fail_first and len(self.calls) == 1:
            raise RuntimeError("publish failed")
        for name in ("affective-state.json", "affective-context.json",
                     "perception-correlation.json", "focus-emotion.json"):
            if not (self.state_dir / name).is_file():
                raise AssertionError(f"publish before persistence: {name}")
        return object()


class AffectiveCompositionCognitiveBridgeTest(unittest.TestCase):
    def build(self, tmp):
        return build_affective_composition(
            config_root=ROOT, state_dir=Path(tmp), now=lambda: NOW,
            id_factory=lambda: "inc-1", expected_sha="a" * 40)

    def test_publish_happens_after_a1_a2_a3_a4_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = self.build(tmp)
            recorder = RecordingPublisher(tmp)
            comp.cognitive_publisher = recorder
            result = comp.processar(stim(
                "x99-bridge-1", "managed.x99",
                {"channel_status": "healthy", "reads": {}},
            ))
            self.assertTrue(result.aceito)
            self.assertEqual(1, len(recorder.calls))
            self.assertIs(recorder.calls[0][1], result.resultado_percepcao)
            self.assertEqual("x99-bridge-1", recorder.calls[0][4][-1].stimulus_id)
            status = comp.cognitive_bridge_status()
            self.assertEqual("x99-bridge-1", status["last_publish_stimulus_id"])
            self.assertIsNone(status["current_error"])

    def test_duplicate_and_unmapped_source_do_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = self.build(tmp)
            recorder = RecordingPublisher(tmp)
            comp.cognitive_publisher = recorder
            event = stim("x99-bridge-dup", "managed.x99", {"channel_status": "healthy", "reads": {}})
            self.assertTrue(comp.processar(event).aceito)
            self.assertFalse(comp.processar(event).aceito)
            self.assertIsNone(comp.processar(stim("wifi-x", "wifi.presence", {"zone": "WIFI_OBSERVED"})))
            self.assertEqual(1, len(recorder.calls))

    def test_publish_failure_is_current_and_recovers_on_next_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = self.build(tmp)
            recorder = RecordingPublisher(tmp, fail_first=True)
            comp.cognitive_publisher = recorder
            first = comp.processar(stim("x99-bridge-fail", "managed.x99", {"channel_status": "healthy", "reads": {}}))
            self.assertTrue(first.aceito)
            self.assertEqual("publish:RuntimeError", comp.cognitive_bridge_status()["current_error"])
            second = comp.processar(stim("x99-bridge-ok", "managed.x99", {"channel_status": "healthy", "reads": {}}))
            self.assertTrue(second.aceito)
            status = comp.cognitive_bridge_status()
            self.assertIsNone(status["current_error"])
            self.assertEqual("x99-bridge-ok", status["last_publish_stimulus_id"])
            self.assertTrue(any(x == "publish:RuntimeError" for x in comp.cognitive_bridge_diagnostics()))


if __name__ == "__main__":
    unittest.main()
