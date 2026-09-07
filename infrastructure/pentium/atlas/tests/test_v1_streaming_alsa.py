import unittest

from infrastructure.pentium.atlas.alsa_stream import SubprocessPcmFrameSource


class FakeStdout:
    def __init__(self, payload): self.payload = payload
    def read(self, count): return self.payload[:count]

class FakeProc:
    def __init__(self, payload):
        self.stdout = FakeStdout(payload); self.terminated = False; self.waited = False
    def terminate(self): self.terminated = True
    def wait(self, timeout=None): self.waited = True

class StreamingAlsaTests(unittest.TestCase):
    def test_reads_exact_20ms_pcm_frame_and_closes_process(self):
        proc = FakeProc(b'x' * 640)
        src = SubprocessPcmFrameSource(proc, frame_bytes=640)
        self.assertEqual(640, len(src.read_frame()))
        src.close()
        self.assertTrue(proc.terminated)
        self.assertTrue(proc.waited)
