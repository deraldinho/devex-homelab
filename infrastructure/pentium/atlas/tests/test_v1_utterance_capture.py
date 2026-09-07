import io
import struct
import unittest
import wave

from infrastructure.pentium.atlas.utterance_capture import StreamingUtteranceCapture


class FakeFrameSource:
    def __init__(self, amplitudes):
        self.frames = [self._pcm(a) for a in amplitudes]
        self.closed = False

    @staticmethod
    def _pcm(amplitude):
        return b''.join(struct.pack('<h', amplitude if i % 2 == 0 else -amplitude) for i in range(320))

    def read_frame(self):
        return self.frames.pop(0) if self.frames else b''

    def close(self):
        self.closed = True

class FixedDetector:
    def __init__(self, threshold=2000): self.threshold = threshold
    def is_speech_frame(self, frame):
        samples = [x[0] for x in struct.iter_unpack('<h', frame)]
        rms = (sum(v*v for v in samples) / len(samples)) ** 0.5
        return rms >= self.threshold


class StreamingUtteranceCaptureTests(unittest.TestCase):
    def test_segments_voice_and_stops_after_trailing_silence(self):
        amplitudes = [500] * 5 + [3500] * 12 + [500] * 6
        source = FakeFrameSource(amplitudes)
        capture = StreamingUtteranceCapture(
            lambda: source, FixedDetector(), frame_ms=20,
            start_speech_frames=3, trailing_silence_ms=100, max_utterance_s=2,
            pre_roll_ms=40,
        )
        audio = capture.capture_utterance()
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            self.assertEqual(1, wav.getnchannels())
            self.assertEqual(16000, wav.getframerate())
            self.assertLess(wav.getnframes(), len(amplitudes) * 320)
        self.assertTrue(source.closed)

class StreamingUtteranceSilenceTests(unittest.TestCase):
    def test_no_speech_returns_after_bounded_listen_window(self):
        source = FakeFrameSource([500] * 200)
        capture = StreamingUtteranceCapture(
            lambda: source, FixedDetector(), frame_ms=20,
            start_speech_frames=3, trailing_silence_ms=800,
            max_utterance_s=12, pre_roll_ms=200, listen_window_s=1,
        )
        audio = capture.capture_utterance()
        self.assertEqual(b'', audio)
        self.assertEqual(150, len(source.frames))
