import unittest

from infrastructure.pentium.atlas.voice_runtime import VoiceRuntime, VoiceState
from infrastructure.pentium.atlas.voice_gate import WakePhraseGate


class FakeCapture:
    def capture_utterance(self): return b"pcm"
class FakeVad:
    def __init__(self, speech=True): self.speech=speech
    def has_speech(self, audio): return self.speech
class FakeStt:
    def __init__(self, text): self.text=text; self.calls=[]
    def transcribe(self, audio): self.calls.append(audio); return self.text
class FakeInteraction:
    def __init__(self): self.calls=[]
    def handle(self, text): self.calls.append(text); return "Estou operacional."
class FakeTts:
    def __init__(self): self.calls=[]
    def speak(self, text): self.calls.append(text)


class VoiceRuntimeTests(unittest.TestCase):
    def test_silence_skips_stt_cognition_and_tts(self):
        stt, interaction, tts = FakeStt("Atlas, oi"), FakeInteraction(), FakeTts()
        runtime = VoiceRuntime(FakeCapture(), stt, WakePhraseGate("Atlas", max_text_chars=256), interaction, tts, vad=FakeVad(False))
        result = runtime.run_once()
        self.assertEqual([], stt.calls); self.assertEqual([], interaction.calls); self.assertEqual([], tts.calls)
        self.assertEqual("no_speech", result.reason)

    def test_wake_phrase_flows_to_interaction_and_live_tts(self):
        interaction, tts = FakeInteraction(), FakeTts()
        runtime = VoiceRuntime(FakeCapture(), FakeStt("Atlas, como voce esta?"), WakePhraseGate("Atlas", max_text_chars=256), interaction, tts, vad=FakeVad())
        result = runtime.run_once()
        self.assertEqual(["como voce esta?"], interaction.calls); self.assertEqual(["Estou operacional."], tts.calls)
        self.assertEqual(VoiceState.LISTENING, result.state)

    def test_non_wake_phrase_is_discarded_without_llm_or_tts(self):
        interaction, tts = FakeInteraction(), FakeTts()
        runtime = VoiceRuntime(FakeCapture(), FakeStt("como voce esta?"), WakePhraseGate("Atlas", max_text_chars=256), interaction, tts, vad=FakeVad())
        result = runtime.run_once()
        self.assertEqual([], interaction.calls); self.assertEqual([], tts.calls); self.assertEqual("wake_phrase_missing", result.reason)

if __name__ == "__main__": unittest.main()


class VoiceRuntimeNoiseFilterTests(unittest.TestCase):
    def test_non_speech_caption_is_discarded_before_wake_gate(self):
        from infrastructure.pentium.atlas.transcript_filter import NonSpeechTranscriptFilter
        interaction, tts = FakeInteraction(), FakeTts()
        runtime = VoiceRuntime(
            FakeCapture(), FakeStt('[MÚSICA DE FUNDO]'), WakePhraseGate('Atlas', max_text_chars=256),
            interaction, tts, vad=FakeVad(), transcript_filter=NonSpeechTranscriptFilter(),
        )
        result = runtime.run_once()
        self.assertEqual([], interaction.calls)
        self.assertEqual([], tts.calls)
        self.assertEqual('non_speech_transcript', result.reason)

class EmptyCapture:
    def capture_utterance(self): return b''

class VoiceRuntimeEmptyCaptureTests(unittest.TestCase):
    def test_empty_capture_skips_stt(self):
        stt, interaction, tts = FakeStt('Atlas, oi'), FakeInteraction(), FakeTts()
        runtime = VoiceRuntime(EmptyCapture(), stt, WakePhraseGate('Atlas', max_text_chars=256), interaction, tts)
        result = runtime.run_once()
        self.assertEqual('no_speech', result.reason)
        self.assertEqual([], stt.calls)
