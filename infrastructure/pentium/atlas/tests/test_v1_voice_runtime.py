import unittest

from infrastructure.pentium.atlas.voice_runtime import VoiceRuntime, VoiceState
from infrastructure.pentium.atlas.voice_gate import WakePhraseGate


class FakeCapture:
    def capture_utterance(self):
        return b"pcm"


class FakeStt:
    def __init__(self, text): self.text = text
    def transcribe(self, audio): return self.text


class FakeInteraction:
    def __init__(self): self.calls = []
    def handle(self, text):
        self.calls.append(text)
        return "Estou operacional."


class FakeTts:
    def __init__(self): self.calls = []
    def speak(self, text): self.calls.append(text)


class VoiceRuntimeTests(unittest.TestCase):
    def test_wake_phrase_flows_to_interaction_and_live_tts(self):
        interaction, tts = FakeInteraction(), FakeTts()
        runtime = VoiceRuntime(FakeCapture(), FakeStt("Atlas, como voce esta?"), WakePhraseGate("Atlas", max_text_chars=256), interaction, tts)
        result = runtime.run_once()
        self.assertEqual(["como voce esta?"], interaction.calls)
        self.assertEqual(["Estou operacional."], tts.calls)
        self.assertEqual(VoiceState.LISTENING, result.state)

    def test_non_wake_phrase_is_discarded_without_llm_or_tts(self):
        interaction, tts = FakeInteraction(), FakeTts()
        runtime = VoiceRuntime(FakeCapture(), FakeStt("como voce esta?"), WakePhraseGate("Atlas", max_text_chars=256), interaction, tts)
        result = runtime.run_once()
        self.assertEqual([], interaction.calls)
        self.assertEqual([], tts.calls)
        self.assertEqual("wake_phrase_missing", result.reason)


if __name__ == "__main__":
    unittest.main()
