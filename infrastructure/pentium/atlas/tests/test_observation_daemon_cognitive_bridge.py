import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.pentium.atlas.observation_daemon import _health_payload, build_observation_context
from infrastructure.pentium.atlas.stimulus_model import Stimulus, StimulusSeverity
from infrastructure.pentium.atlas.tests.test_affective_composition_cognitive_bridge import RecordingPublisher
from infrastructure.pentium.atlas.tests.test_observation_daemon import (
    AGENT_CONFIG, ATLAS, EmptyScanner, FakeListener, ManagedService,
)


def current_stimulus(sid):
    now = datetime.now(timezone.utc).isoformat()
    return Stimulus(sid, "managed.x99", "status_changed", StimulusSeverity.NOTICE,
                    now, {"channel_status": "healthy", "reads": {}}, 1.0, sid)


class ObservationDaemonCognitiveBridgeTest(unittest.TestCase):
    def test_health_tracks_current_bridge_error_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            context = build_observation_context(
                config_root=ATLAS, agent_config_path=AGENT_CONFIG, state_dir=Path(tmp),
                wifi_interface="wlan0", managed_read_service=ManagedService(), scanner=EmptyScanner(),
                interaction_listener=FakeListener(), expected_sha="a" * 40)
            try:
                context.composition.cognitive_publisher = RecordingPublisher(tmp, fail_first=True)
                context.composition.processar(current_stimulus("bridge-fail"))
                degraded = _health_payload(context)
                self.assertEqual("degraded", degraded["status"])
                self.assertEqual(["publish:RuntimeError"], degraded["errors"]["cognitive_bridge"])

                context.composition.processar(current_stimulus("bridge-ok"))
                healthy = _health_payload(context)
                self.assertEqual("healthy", healthy["status"])
                self.assertEqual([], healthy["errors"]["cognitive_bridge"])
            finally:
                context.close()


if __name__ == "__main__":
    unittest.main()
