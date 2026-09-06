import inspect
import unittest

from infrastructure.pentium.atlas.sampler_linux_cognitivo import LinuxCognitiveSampler


class LinuxCognitiveSamplerDefaultsTests(unittest.TestCase):
    def test_fontes_fisicas_ambiguas_nao_tem_default_inventado(self):
        params = inspect.signature(LinuxCognitiveSampler.__init__).parameters
        self.assertIsNone(params['thermal_path'].default)
        self.assertIsNone(params['llm_status_path'].default)
