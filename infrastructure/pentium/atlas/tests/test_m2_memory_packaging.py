import unittest
from pathlib import Path


M2_MODULES = (
    "episodic_model.py",
    "episodic_buffer.py",
    "episodic_consolidator.py",
    "episodic_adapters.py",
    "episodic_ingestion.py",
    "episodic_metrics.py",
)


class MemoryM2PackagingTests(unittest.TestCase):
    def test_installer_empacota_modulos_m2_e_preserva_m1(self):
        text = Path("infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        for name in M2_MODULES:
            self.assertIn(name, text)
        self.assertIn("ATLAS_MEMORY_M1_INSTALL_PASS", text)
        self.assertIn("ATLAS_MEMORY_M2_INSTALL_PASS", text)
        self.assertNotIn("systemctl --user enable --now atlas", text)

    def test_ci_compila_executa_e_marca_m2(self):
        text = Path(".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        for name in M2_MODULES:
            self.assertIn(name, text)
        self.assertIn("test_episodic_model", text)
        self.assertIn("test_episodic_buffer", text)
        self.assertIn("test_episodic_consolidator", text)
        self.assertIn("test_episodic_adapters", text)
        self.assertIn("test_episodic_ingestion", text)
        self.assertIn(
            "echo 'DEVEX_HOMELAB_ATLAS_MEMORY_M2_PASS'",
            [line.strip() for line in text.splitlines()],
        )


if __name__ == "__main__":
    unittest.main()
