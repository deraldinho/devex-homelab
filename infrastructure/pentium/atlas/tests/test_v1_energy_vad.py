import io, struct, unittest, wave

from infrastructure.pentium.atlas.energy_vad import EnergyVad


def wav(samples):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", x) for x in samples))
    return out.getvalue()


class EnergyVadTests(unittest.TestCase):
    def test_silence_is_rejected(self):
        vad = EnergyVad(rms_threshold=200, max_samples=32000)
        self.assertFalse(vad.has_speech(wav([0] * 1600)))

    def test_loud_signal_is_accepted(self):
        vad = EnergyVad(rms_threshold=200, max_samples=32000)
        self.assertTrue(vad.has_speech(wav([1000, -1000] * 800)))

    def test_non_pcm_or_oversized_is_rejected(self):
        vad = EnergyVad(rms_threshold=200, max_samples=100)
        self.assertFalse(vad.has_speech(b"not-wave"))
        self.assertFalse(vad.has_speech(wav([1000] * 101)))


if __name__ == "__main__": unittest.main()
