import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from infrastructure.pentium.atlas.voice_health import VoiceHealthPublisher


class VoiceHealthPublisherTests(unittest.TestCase):
    def test_publishes_atomic_bounded_health_with_exact_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "voice-health.json"
            publisher = VoiceHealthPublisher(
                path, now=lambda: "2026-09-12T13:00:00+00:00"
            )
            with patch.object(os, "chmod") as chmod:
                publisher.publish(
                    status="healthy", state="LISTENING",
                    reason="x" * 400, expected_sha="a" * 40,
                )
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("healthy", payload["status"])
        self.assertEqual("LISTENING", payload["state"])
        self.assertEqual("a" * 40, payload["expected_sha"])
        self.assertLessEqual(len(payload["reason"]), 256)
        self.assertEqual("2026-09-12T13:00:00+00:00", payload["generated_at"])
        chmod.assert_called_once()
