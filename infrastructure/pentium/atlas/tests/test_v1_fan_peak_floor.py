import io, struct, unittest, wave

from infrastructure.pentium.atlas.adaptive_vad import AdaptiveEnergyVad


def make_wav(frame_amplitudes, samples_per_value=320):
    raw=[]
    for amp in frame_amplitudes:
        for i in range(samples_per_value):
            raw.append(struct.pack('<h', amp if i % 2 == 0 else -amp))
    out=io.BytesIO()
    with wave.open(out,'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b''.join(raw))
    return out.getvalue()


class FanPeakFloorTests(unittest.TestCase):
    def test_calibration_tracks_p95_and_rejects_periodic_fan_bursts(self):
        vad = AdaptiveEnergyVad(min_rms_threshold=220, snr_ratio=1.15, margin=150,
                                calibration_frames=1, frame_ms=20, min_speech_frames=5,
                                max_samples=64000)
        fan=[700]*170+[5200]*20+[10000]*10
        self.assertFalse(vad.has_speech(make_wav(fan)))
        self.assertGreater(vad.noise_peak_floor, 4000)
        self.assertFalse(vad.has_speech(make_wav(fan)))
    def test_voice_burst_still_exceeds_peak_floor(self):
        vad = AdaptiveEnergyVad(min_rms_threshold=220, snr_ratio=1.15, margin=150,
                                calibration_frames=1, frame_ms=20, min_speech_frames=5,
                                max_samples=64000)
        fan=[700]*190+[5000]*10
        self.assertFalse(vad.has_speech(make_wav(fan)))
        voice=[700]*80+[9000]*12+[700]*108
        self.assertTrue(vad.has_speech(make_wav(voice)))


if __name__ == '__main__':
    unittest.main()
