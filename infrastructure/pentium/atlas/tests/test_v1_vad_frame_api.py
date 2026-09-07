import struct, unittest
from infrastructure.pentium.atlas.adaptive_vad import AdaptiveEnergyVad

class AdaptiveVadFrameApiTests(unittest.TestCase):
    def test_frame_api_uses_current_noise_envelope(self):
        vad = AdaptiveEnergyVad(calibration_frames=0, snr_ratio=1.15, margin=150, frame_ms=20)
        vad._noise_floor = 1000.0
        vad._noise_peak_floor = 2500.0
        low = b''.join(struct.pack('<h', 2200 if i % 2 == 0 else -2200) for i in range(320))
        high = b''.join(struct.pack('<h', 4000 if i % 2 == 0 else -4000) for i in range(320))
        self.assertFalse(vad.is_speech_frame(low))
        self.assertTrue(vad.is_speech_frame(high))
