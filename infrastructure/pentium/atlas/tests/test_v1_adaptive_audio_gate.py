import io
import struct
import unittest
import wave

from infrastructure.pentium.atlas.adaptive_vad import AdaptiveEnergyVad
from infrastructure.pentium.atlas.transcript_filter import NonSpeechTranscriptFilter


def wav_with_amplitude(amplitude: int, frames: int = 16000) -> bytes:
    raw = b''.join(struct.pack('<h', amplitude if i % 2 == 0 else -amplitude) for i in range(frames))
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(raw)
    return out.getvalue()


class AdaptiveEnergyVadTests(unittest.TestCase):
    def test_calibrates_stationary_fan_then_accepts_voice_above_noise_floor(self):
        vad = AdaptiveEnergyVad(min_rms_threshold=220, snr_ratio=1.8, margin=80, calibration_frames=1, max_samples=32000)
        self.assertFalse(vad.has_speech(wav_with_amplitude(500)))
        self.assertFalse(vad.has_speech(wav_with_amplitude(520)))
        self.assertTrue(vad.has_speech(wav_with_amplitude(1400)))
        self.assertGreaterEqual(vad.noise_floor, 500)


class NonSpeechTranscriptFilterTests(unittest.TestCase):
    def test_discards_only_full_non_speech_caption(self):
        filt = NonSpeechTranscriptFilter()
        self.assertEqual('', filt.clean('[MÚSICA DE FUNDO]'))
        self.assertEqual('', filt.clean('ruído'))
        self.assertEqual('Atlas, tem uma música de fundo aqui', filt.clean('Atlas, tem uma música de fundo aqui'))


if __name__ == '__main__':
    unittest.main()


class AdaptiveFrameVadTests(unittest.TestCase):
    def test_stationary_server_fan_is_ignored_but_speech_burst_is_detected(self):
        vad = AdaptiveEnergyVad(
            min_rms_threshold=220, snr_ratio=1.15, margin=150,
            calibration_frames=1, frame_ms=20, min_speech_frames=5, max_samples=32000,
        )
        self.assertFalse(vad.has_speech(wav_with_amplitude(3000)))
        self.assertFalse(vad.has_speech(wav_with_amplitude(3100)))
        mixed = []
        for i in range(16000):
            amp = 4300 if 6000 <= i < 10000 else 3000
            mixed.append(struct.pack('<h', amp if i % 2 == 0 else -amp))
        out = io.BytesIO()
        with wave.open(out, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b''.join(mixed))
        self.assertTrue(vad.has_speech(out.getvalue()))
