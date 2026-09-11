import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.sampler_linux_cognitivo import LinuxCognitiveSampler


class LinuxCognitiveSamplerTests(unittest.TestCase):
    def test_coleta_memoria_swap_cpu_temperatura_e_rss_atlas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meminfo").write_text(
                "MemTotal: 3000000 kB\nSwapTotal: 1000000 kB\nSwapFree: 750000 kB\n",
                encoding="utf-8",
            )
            (root / "stat").write_text("cpu  100 0 50 850 0 0 0 0 0 0\n", encoding="utf-8")
            (root / "thermal").write_text("57000\n", encoding="utf-8")
            (root / "atlas_status").write_text("VmRSS:\t1234 kB\n", encoding="utf-8")
            sampler = LinuxCognitiveSampler(
                meminfo_path=root / "meminfo",
                proc_stat_path=root / "stat",
                thermal_path=root / "thermal",
                atlas_status_path=root / "atlas_status",
            )
            m = sampler.coletar()
            self.assertEqual(1234, m.rss_atlas_kib)
            self.assertIsNone(m.rss_llm_kib)
            self.assertEqual(250000, m.swap_usada_kib)
            self.assertIsNone(m.cpu_percent)
            self.assertEqual(57.0, m.temperatura_c)
            (root / "stat").write_text("cpu  120 0 50 930 0 0 0 0 0 0\n", encoding="utf-8")
            self.assertEqual(20.0, sampler.coletar().cpu_percent)

    def test_fonte_ausente_vira_none_sem_excecao(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sampler = LinuxCognitiveSampler(
                meminfo_path=root / "missing",
                proc_stat_path=root / "missing2",
                thermal_path=root / "missing3",
                atlas_status_path=root / "missing4",
            )
            m = sampler.coletar()
            self.assertIsNone(m.temperatura_c)
            self.assertIsNone(m.rss_llm_kib)


if __name__ == "__main__":
    unittest.main()
