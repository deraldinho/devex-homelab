import socket
import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.affective_interaction_ipc import (
    InteractionDatagramClient,
    InteractionDatagramListener,
    decode_interaction,
    encode_interaction,
)
from infrastructure.pentium.atlas.modelo_visual_atlas import EstadoInteracaoVisual

NOW = "2026-09-08T06:10:00+00:00"


class AffectiveInteractionIpcTests(unittest.TestCase):
    def state(self, **flags):
        return EstadoInteracaoVisual(atualizado_em=NOW, **flags)

    def test_payload_is_versioned_bounded_and_contains_only_flags(self):
        raw = encode_interaction(self.state(pensando=True))
        self.assertLessEqual(len(raw), 512)
        text = raw.decode("utf-8")
        self.assertIn('"schema_version":1', text)
        self.assertNotIn("transcript", text)
        self.assertNotIn("audio", text)

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "AF_UNIX unavailable on this host")
    def test_local_datagram_reaches_single_sink(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "interaction.sock"
            received = []
            listener = InteractionDatagramListener(path, received.append)
            listener.start()
            try:
                self.assertTrue(InteractionDatagramClient(path).send(self.state(falando=True)))
                self.assertTrue(listener.run_once(timeout_s=1.0))
                self.assertTrue(received[0].falando)
            finally:
                listener.close()
            self.assertFalse(path.exists())

    def test_decoder_rejects_unknown_schema_without_transport(self):
        with self.assertRaises(ValueError):
            decode_interaction(b'{"schema_version":2}')

    def test_client_is_fail_safe_when_listener_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.sock"
            self.assertFalse(InteractionDatagramClient(path).send(self.state(ouvindo=True)))

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "AF_UNIX unavailable on this host")
    def test_invalid_datagram_is_dropped_without_sink_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "interaction.sock"
            received = []
            listener = InteractionDatagramListener(path, received.append)
            listener.start()
            try:
                sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                try:
                    sender.sendto(b'{"schema_version":2}', str(path))
                finally:
                    sender.close()
                self.assertFalse(listener.run_once(timeout_s=1.0))
                self.assertEqual([], received)
            finally:
                listener.close()


if __name__ == "__main__":
    unittest.main()
