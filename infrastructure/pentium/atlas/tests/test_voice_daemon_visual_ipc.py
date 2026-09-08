import inspect
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoInteracaoVisual
from infrastructure.pentium.atlas.voice_daemon import build_runtime, build_visual_state_sink

NOW = "2026-09-08T06:20:00+00:00"


class VoiceDaemonVisualIpcTests(unittest.TestCase):
    def test_visual_sink_is_fail_safe_when_observation_daemon_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            sink = build_visual_state_sink(Path(tmp) / "missing.sock")
            state = EstadoInteracaoVisual(ouvindo=True, atualizado_em=NOW)
            self.assertFalse(sink(state))

    def test_build_runtime_wires_ipc_sink_instead_of_visual_writer(self):
        source = inspect.getsource(build_runtime)
        self.assertIn("visual_state_sink=build_visual_state_sink()", source)
        self.assertNotIn("VisualStatePublisher", source)


if __name__ == "__main__":
    unittest.main()
