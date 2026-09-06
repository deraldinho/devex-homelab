import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from infrastructure.pentium.atlas.fontes_fisicas_cognitivas import descobrir_fonte_termica, status_path_para_pid


class FontesFisicasCognitivasTests(unittest.TestCase):
    def test_status_path_exige_pid_real_positivo(self):
        self.assertEqual(Path('/proc/123/status'), status_path_para_pid(123))
        for pid in (0, -1):
            with self.assertRaises(ValueError):
                status_path_para_pid(pid)

    def test_prefere_thermal_cpu_e_registra_tipo(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            z0 = root / 'thermal_zone0'; z0.mkdir()
            (z0 / 'type').write_text('acpitz\n'); (z0 / 'temp').write_text('41000\n')
            z1 = root / 'thermal_zone1'; z1.mkdir()
            (z1 / 'type').write_text('x86_pkg_temp\n'); (z1 / 'temp').write_text('52000\n')
            fonte = descobrir_fonte_termica(root)
            self.assertEqual('x86_pkg_temp', fonte.tipo)
            self.assertEqual(z1 / 'temp', fonte.path)
