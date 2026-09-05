import tempfile
import unittest
from pathlib import Path

from infrastructure.pentium.atlas.fontes_fisicas_cognitivas import descobrir_fonte_termica, status_path_para_pid


class FontesFisicasCognitivasTests(unittest.TestCase):
    def test_status_path_exige_pid_real_positivo(self):
        with self.assertRaises(ValueError):
            status_path_para_pid(0)
        self.assertEqual(Path('/proc/123/status'), status_path_para_pid(123))

    def test_prefere_thermal_cpu_e_registra_tipo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'thermal_zone0').mkdir(); (root / 'thermal_zone0' / 'type').write_text('acpitz\n', encoding='utf-8'); (root / 'thermal_zone0' / 'temp').write_text('45000\n', encoding='utf-8')
            (root / 'thermal_zone1').mkdir(); (root / 'thermal_zone1' / 'type').write_text('x86_pkg_temp\n', encoding='utf-8'); (root / 'thermal_zone1' / 'temp').write_text('52000\n', encoding='utf-8')
            fonte = descobrir_fonte_termica(root)
            self.assertEqual('x86_pkg_temp', fonte.tipo)
            self.assertEqual(root / 'thermal_zone1' / 'temp', fonte.path)


if __name__ == '__main__':
    unittest.main()
