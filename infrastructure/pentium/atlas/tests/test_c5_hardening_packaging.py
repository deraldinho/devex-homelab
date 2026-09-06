import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


class C5HardeningPackagingTests(unittest.TestCase):
    def test_installer_empacota_fontes_sem_pass_fisico(self):
        text = (ROOT / 'infrastructure/pentium/atlas/install-user.sh').read_text(encoding='utf-8')
        self.assertIn('fontes_fisicas_cognitivas.py', text)
        self.assertIn('ATLAS_COGNITIVO_C5_HARDENING_INSTALL_PASS', text)
        self.assertNotIn('ATLAS_COGNITIVO_C5_PHYSICAL_PASS', text)

    def test_ci_compila_e_marca_hardening_sem_pass_fisico(self):
        text = (ROOT / '.github/workflows/foundation-ci.yml').read_text(encoding='utf-8')
        self.assertIn('fontes_fisicas_cognitivas.py', text)
        self.assertIn("echo 'DEVEX_HOMELAB_ATLAS_COGNITIVO_C5_HARDENING_PASS'", text)
        self.assertNotIn('ATLAS_COGNITIVO_C5_PHYSICAL_PASS', text)
