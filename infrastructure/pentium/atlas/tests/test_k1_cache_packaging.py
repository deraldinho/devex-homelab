import unittest
from pathlib import Path


class K1CachePackagingTests(unittest.TestCase):
    def test_installer_empacota_k1_sem_start_automatico(self):
        text = Path("infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        for name in ("cognitive_cache.py", "config_cache.py", "config_cache.json"):
            self.assertIn(name, text)
        self.assertIn("ATLAS_COGNITIVE_CACHE_K1_INSTALL_PASS", text)
        self.assertNotIn("systemctl --user enable --now atlas", text)

    def test_ci_compila_valida_e_marca_k1(self):
        text = Path(".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        for name in ("cognitive_cache.py", "config_cache.py", "config_cache.json"):
            self.assertIn(name, text)
        lines = [line.strip() for line in text.splitlines()]
        self.assertIn("echo 'DEVEX_HOMELAB_ATLAS_COGNITIVE_CACHE_K1_PASS'", lines)


if __name__ == "__main__":
    unittest.main()