import unittest

from infrastructure.pentium.atlas.voice_gate import WakePhraseGate


class WakePhraseGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = WakePhraseGate("Atlas", max_text_chars=256)

    def test_accepts_prefix_and_strips_wake_phrase(self):
        result = self.gate.evaluate("Atlas, como esta o x99?")
        self.assertTrue(result.activated)
        self.assertEqual("como esta o x99?", result.command_text)

    def test_rejects_text_without_wake_phrase(self):
        result = self.gate.evaluate("como esta o x99?")
        self.assertFalse(result.activated)
        self.assertIsNone(result.command_text)

    def test_rejects_oversized_transcript(self):
        with self.assertRaises(ValueError):
            self.gate.evaluate("Atlas " + ("x" * 300))


if __name__ == "__main__":
    unittest.main()
