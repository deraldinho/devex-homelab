import unittest
from pathlib import Path


class MemoryM1PackagingTests(unittest.TestCase):
    def test_installer_empacota_memoria_sem_start_automatico(self):
        text = Path("infrastructure/pentium/atlas/install-user.sh").read_text(encoding="utf-8")
        for name in (
            "memory_model.py", "memory_store.py", "memory_manager.py",
            "memory_retriever.py", "config_memory.py", "config_memory.json",
        ):
            self.assertIn(name, text)
        self.assertIn("ATLAS_MEMORY_M1_INSTALL_PASS", text)
        self.assertNotIn("systemctl --user enable --now atlas", text)

    def test_ci_compila_valida_e_marca_memory_m1(self):
        text = Path(".github/workflows/foundation-ci.yml").read_text(encoding="utf-8")
        for name in ("memory_model.py", "memory_store.py", "memory_manager.py", "memory_retriever.py", "config_memory.py"):
            self.assertIn(name, text)
        self.assertIn("config_memory.json", text)
        self.assertIn("echo 'DEVEX_HOMELAB_ATLAS_MEMORY_M1_PASS'", [line.strip() for line in text.splitlines()])


if __name__ == "__main__":
    unittest.main()
