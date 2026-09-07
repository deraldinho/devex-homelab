import struct, unittest
from infrastructure.pentium.atlas.streaming_vad import StreamingAdaptiveVad


def frame(amplitude):
    return b''.join(struct.pack('<h', amplitude if i % 2 == 0 else -amplitude) for i in range(320))

class StreamingAdaptiveVadTests(unittest.TestCase):
    def test_calibrates_fan_then_detects_voice(self):
        vad = StreamingAdaptiveVad(calibration_frames=5, history_frames=20, snr_ratio=1.15, margin=150)
        for amp in (800, 900, 5000, 850, 1000):
            self.assertFalse(vad.is_speech_frame(frame(amp)))
        self.assertFalse(vad.is_speech_frame(frame(1000)))
        self.assertTrue(vad.is_speech_frame(frame(8000)))

    def test_history_is_bounded(self):
        vad = StreamingAdaptiveVad(calibration_frames=1, history_frames=8)
        for _ in range(30): vad.is_speech_frame(frame(700))
        self.assertLessEqual(vad.history_size, 8)
