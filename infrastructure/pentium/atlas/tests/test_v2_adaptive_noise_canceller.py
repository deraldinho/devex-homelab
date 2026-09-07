import math
import struct
import unittest

from infrastructure.pentium.atlas.adaptive_noise_canceller import NlmsCanceller, AdaptiveNoiseCancelledFrameSource


def rms(values):
    return math.sqrt(sum(v*v for v in values) / len(values))


class NlmsCancellerTests(unittest.TestCase):
    def test_calibrates_on_noise_then_freezes_weights_during_voice(self):
        ref = [int(5000 * math.sin(i * 0.17)) for i in range(5000)]
        canceller = NlmsCanceller(taps=16, mu=0.3, epsilon=1.0)
        for i in range(1500):
            canceller.process_sample(int(ref[i] * 0.65), ref[i], adapt=True)
        voice = [2200 if (i // 40) % 2 else -2200 for i in range(1500, 5000)]
        primary = [voice[i-1500] + int(ref[i] * 0.65) for i in range(1500, 5000)]
        cleaned = [canceller.process_sample(primary[j-1500], ref[j], adapt=False) for j in range(1500, 5000)]
        before = rms([primary[i] - voice[i] for i in range(len(voice))])
        after = rms([cleaned[i] - voice[i] for i in range(len(voice))])
        self.assertLess(after, before * 0.2)

class FakeStereoSource:
    def __init__(self, frame): self.frame = frame; self.closed = False
    def read_frame(self): return self.frame
    def close(self): self.closed = True


class AdaptiveNoiseCancelledFrameSourceTests(unittest.TestCase):
    def test_converts_interleaved_stereo_to_mono_cleaned_frame(self):
        samples = [struct.pack('<hh', 1200 if i % 2 else 800, 200) for i in range(320)]
        source = FakeStereoSource(b''.join(samples))
        wrapped = AdaptiveNoiseCancelledFrameSource(
            source, primary_channel='left', reference_channel='right',
            taps=4, mu=0.2, calibration_frames=1,
        )
        out = wrapped.read_frame()
        self.assertEqual(640, len(out))
        wrapped.close()
        self.assertTrue(source.closed)


if __name__ == '__main__': unittest.main()
