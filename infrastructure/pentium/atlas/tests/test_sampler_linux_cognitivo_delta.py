import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.sampler_linux_cognitivo import LinuxCognitiveSampler


class LinuxCognitiveSamplerDeltaTests(unittest.TestCase):
    def test_cpu_usa_delta_entre_amostras(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meminfo = root / "meminfo"; meminfo.write_text("SwapTotal: 1000 kB\nSwapFree: 900 kB\n", encoding="utf-8")
            stat = root / "stat"; stat.write_text("cpu  100 0 0 900 0 0 0 0 0 0\n", encoding="utf-8")
            temp = root / "thermal"; temp.write_text("50000\n", encoding="utf-8")
            atlas = root / "atlas"; atlas.write_text("VmRSS:\t100 kB\n", encoding="utf-8")
            llm = root / "llm"; llm.write_text("VmRSS:\t200 kB\n", encoding="utf-8")
            sampler = LinuxCognitiveSampler(meminfo_path=meminfo, proc_stat_path=stat, thermal_path=temp, atlas_status_path=atlas, llm_status_path=llm)
            self.assertIsNone(sampler.coletar().cpu_percent)
            stat.write_text("cpu  120 0 0 980 0 0 0 0 0 0\n", encoding="utf-8")
            self.assertEqual(20.0, sampler.coletar().cpu_percent)


if __name__ == "__main__":
    unittest.main()
