import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.pentium.atlas.sampler_linux_cognitivo import LinuxCognitiveSampler


class LinuxCognitiveSamplerDeltaTests(unittest.TestCase):
    def test_cpu_usa_delta_entre_amostras(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            stat = root / 'stat'
            meminfo = root / 'meminfo'
            temp = root / 'temp'
            atlas = root / 'atlas'
            llm = root / 'llm'
            meminfo.write_text('SwapTotal: 1000 kB\nSwapFree: 900 kB\n')
            temp.write_text('42000\n')
            atlas.write_text('VmRSS: 100 kB\n')
            llm.write_text('VmRSS: 200 kB\n')
            stat.write_text('cpu  100 0 100 800 0 0 0 0 0 0\n')
            sampler = LinuxCognitiveSampler(meminfo_path=meminfo, proc_stat_path=stat, thermal_path=temp, atlas_status_path=atlas, llm_status_path=llm)
            self.assertIsNone(sampler.coletar().cpu_percent)
            stat.write_text('cpu  150 0 150 900 0 0 0 0 0 0\n')
            self.assertEqual(50.0, sampler.coletar().cpu_percent)
